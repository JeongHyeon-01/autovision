import json
import ffmpeg

# JSON 파일 로드 함수
def load_json(file_path: str):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def scale_and_center(input_clip, width, height, target_width, target_height):
    # Calculate aspect ratios
    input_aspect_ratio = width / height
    target_aspect_ratio = target_width / target_height

    # Determine scaling to maintain aspect ratio and fit the target dimensions
    if input_aspect_ratio > target_aspect_ratio:
        # Image is wider than the target aspect ratio, scale by height
        scale_height = target_height
        scale_width = int(target_height * input_aspect_ratio)
    else:
        # Image is taller or matches aspect ratio, scale by width
        scale_width = target_width
        scale_height = int(target_width / input_aspect_ratio)

    # Scale the image
    input_clip = input_clip.filter('scale', scale_width, scale_height)

    # Ensure padding dimensions are never smaller than the scaled dimensions
    pad_width = max(scale_width, target_width)
    pad_height = max(scale_height, target_height)

    # Apply padding only if needed and with correct dimensions
    if pad_width != scale_width or pad_height != scale_height:
        input_clip = input_clip.filter(
            'pad',
            width=pad_width,
            height=pad_height,
            x='(ow-iw)/2',
            y='(oh-ih)/2',
            color='black'
        )

    # Set pixel format to avoid deprecated warnings
    input_clip = input_clip.filter('format', 'yuv420p')

    return input_clip


def apply_effects(input_clip, effect, clip, target_width, target_height, scale_width, scale_height):
    # Set common parameters
    offset = clip.get('offset', {'x': 0, 'y': 0})
    duration = int(clip['length'] * 25)  # Assuming 25 fps, adjust as needed

    # Apply effects based on the effect type
    if effect == 'zoomOutSlow':
        zoom_speed = 1.002
        initial_zoom = 1.2
        input_clip = input_clip.filter(
            'zoompan',
            z=f'{initial_zoom}/pow({zoom_speed},on)',
            x=f'{offset["x"] * (target_width - 1)}',
            y=f'{offset["y"] * (target_height - 1)}',
            s=f'{target_width}x{target_height}',
            d=duration
        ).filter('setpts', 'PTS-STARTPTS')

    elif effect == 'zoomIn':
        zoom_speed = 1.002
        initial_zoom = 1.0
        input_clip = input_clip.filter(
            'zoompan',
            z=f'{initial_zoom}*pow({zoom_speed},on)',
            x=f'{offset["x"] * (target_width - 1)}',
            y=f'{offset["y"] * (target_height - 1)}',
            s=f'{target_width}x{target_height}',
            d=duration
        ).filter('setpts', 'PTS-STARTPTS')

    elif effect == 'slideLeftFast':
        slide_speed = (scale_width - target_width) / (clip['length'] * 25)
        input_clip = input_clip.filter(
            'fps', fps=25
        ).filter(
            'tpad', stop_mode='clone', stop_duration=clip['length']
        ).filter(
            'setpts', 'PTS-STARTPTS'
        ).filter(
            'pad',
            width=scale_width + target_width,
            height=scale_height,
            x=0,
            y=0,
            color='black'
        ).filter(
            'crop',
            out_w=target_width,
            out_h=target_height,
            x=f'min(iw-{target_width}, n*{slide_speed})',
            y='0'
        )

    elif effect == 'zoomOut':
        zoom_speed = 1.01
        initial_zoom = 1.2
        input_clip = input_clip.filter(
            'zoompan',
            z=f'{initial_zoom}/pow({zoom_speed},on)',
            x=f'{offset["x"] * (target_width - 1)}',
            y=f'{offset["y"] * (target_height - 1)}',
            s=f'{target_width}x{target_height}',
            d=duration
        ).filter('setpts', 'PTS-STARTPTS')

    else:
        # No effect, just set the duration
        input_clip = input_clip.filter('tpad', stop_mode='clone', stop_duration=clip['length'])
        input_clip = input_clip.setpts('PTS-STARTPTS')

    return input_clip


def create_video_from_json(json_data):
    video_clips = []
    audio_clips = []
    output_size = json_data['output']['size']
    target_width = output_size['width']
    target_height = output_size['height']
    target_sar = '1/1'
    total_duration = 0

    for track in json_data['timeline']['tracks']:
        for clip in track['clips']:
            if clip['asset']['type'] == 'image':
                input_clip = ffmpeg.input(clip['asset']['src'])

                # Probe the video stream to get original image dimensions
                probe = ffmpeg.probe(clip['asset']['src'])
                video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                if video_stream:
                    width = int(video_stream['width'])
                    height = int(video_stream['height'])

                    # Scale and center the image to maintain aspect ratio
                    input_clip = scale_and_center(input_clip, width, height, target_width, target_height)

                    # Apply effects based on the specified effect type
                    input_clip = apply_effects(input_clip, clip.get('effect'), clip, target_width, target_height, width, height)

                # Set the duration of the clip to match the specified length
                input_clip = input_clip.filter('trim', duration=clip['length'])

                # Apply standard settings for SAR, FPS, and format
                input_clip = input_clip.filter('setsar', sar=target_sar)
                input_clip = input_clip.filter('fps', fps=25, round='up')
                input_clip = input_clip.filter('format', 'yuv420p')  # Set pixel format

                # Add clip to the sequence, managing start and duration
                if clip['start'] > total_duration:
                    null_duration = clip['start'] - total_duration
                    null_clip = ffmpeg.input('color=c=black:s={}x{}'.format(target_width, target_height), f='lavfi', t=null_duration)
                    null_clip = null_clip.filter('setsar', sar=target_sar)
                    video_clips.append(null_clip)

                video_clips.append(input_clip)
                total_duration = clip['start'] + clip['length']

            elif clip['asset']['type'] == 'audio':
                input_audio = ffmpeg.input(clip['asset']['src'])
                if clip['start'] > 0:
                    silent_audio = ffmpeg.input('anullsrc=r=44100:cl=stereo', f='lavfi', t=clip['start'])
                    audio_clips.append(silent_audio)

                input_audio = input_audio.filter('atrim', duration=clip['length']).filter('apad', whole_dur=clip['length']).filter('aformat', sample_fmts='s16')
                audio_clips.append(input_audio)

    # Combine video and audio clips
    if video_clips:
        output_file = "output_video.mp4"
        video_stream = ffmpeg.concat(*video_clips, v=1, a=0)
        
        if audio_clips:
            audio_stream = ffmpeg.concat(*audio_clips, v=0, a=1)
            output = ffmpeg.output(video_stream, audio_stream, output_file, t=total_duration, vcodec='libx264', acodec='aac', s='{}x{}'.format(target_width, target_height))
        else:
            output = ffmpeg.output(video_stream, output_file, vcodec='libx264', s='{}x{}'.format(target_width, target_height))

        output.run(overwrite_output=True)
        return {"status": "success", "video_url": output_file}
    else:
        return {"status": "error", "message": "No clips found to process"}



# JSON 데이터 로드 및 처리
json_data = load_json('./example.json')
response = create_video_from_json(json_data)
print(response)
