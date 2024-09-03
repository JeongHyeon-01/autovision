import json
import math
import numpy as np
from PIL import Image
from moviepy.editor import *
from moviepy.audio.fx import all as afx  # Ensure audio effects are imported

# JSON 파일 로드 함수
def load_json(file_path: str):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def zoom_in_effect(clip, zoom_ratio=0.04):
    def effect(get_frame, t):
        img = Image.fromarray(get_frame(t))
        base_size = img.size

        new_size = [
            math.ceil(img.size[0] * (1 + (zoom_ratio * t))),
            math.ceil(img.size[1] * (1 + (zoom_ratio * t)))
        ]

        # Ensure dimensions are even
        new_size[0] = new_size[0] + (new_size[0] % 2)
        new_size[1] = new_size[1] + (new_size[1] % 2)

        img = img.resize(new_size, Image.LANCZOS)

        x = math.ceil((new_size[0] - base_size[0]) / 2)
        y = math.ceil((new_size[1] - base_size[1]) / 2)

        img = img.crop([x, y, new_size[0] - x, new_size[1] - y]).resize(base_size, Image.LANCZOS)

        result = np.array(img)
        img.close()
        return result

    return clip.fl(effect)

def zoom_out_effect(clip, zoom_max_ratio=0.5, zoom_out_factor=0.1):
    def effect(get_frame, t):
        img = Image.fromarray(get_frame(t))
        base_size = img.size

        # Calculate the current scale factor based on time
        scale_factor = zoom_max_ratio - (zoom_out_factor * t)
        scale_factor = max(scale_factor, 0)  # Prevent negative scaling

        # Calculate new size maintaining the zoom factor
        new_size = [
            math.ceil(base_size[0] * (1 + scale_factor)),
            math.ceil(base_size[1] * (1 + scale_factor))
        ]

        # Ensure new dimensions are even
        new_size[0] = new_size[0] - (new_size[0] % 2)
        new_size[1] = new_size[1] - (new_size[1] % 2)

        # Resize the image to the new size
        img = img.resize(new_size, Image.LANCZOS)

        # Calculate centered crop coordinates to keep the effect centered
        x_center = new_size[0] // 2
        y_center = new_size[1] // 2
        x = x_center - (base_size[0] // 2)
        y = y_center - (base_size[1] // 2)

        # Crop the image to the original size, centered
        img = img.crop([
            x, y, x + base_size[0], y + base_size[1]
        ])

        # Resize back to the original size to ensure consistent output
        img = img.resize(base_size, Image.LANCZOS)

        result = np.array(img)
        img.close()
        return result

    return clip.fl(effect)

def apply_effects(clip, effect, duration):
    if effect == 'zoomOut':
        return zoom_out_effect(clip, zoom_max_ratio=0.3, zoom_out_factor=0.5)
    elif effect == 'zoomOutSlow':
        return zoom_out_effect(clip, zoom_max_ratio=0.3, zoom_out_factor=0.25)
    elif effect == 'zoomOutFast':
        return zoom_out_effect(clip, zoom_max_ratio=0.3, zoom_out_factor=0.75)
    elif effect == 'zoomIn':
        return zoom_in_effect(clip, zoom_ratio=0.04)
    elif effect == 'slideLeft':
        slide_distance = clip.w + 100
        return clip.set_position(lambda t: (int(-t * slide_distance / duration * 0.25), 'center'))
    elif effect == 'slideLeftFast':
        slide_distance = clip.w + 100
        return clip.set_position(lambda t: (int(-t * slide_distance / duration * 0.5), 'center'))
    elif effect == 'slideLeftSlow':
        slide_distance = clip.w + 100
        return clip.set_position(lambda t: (int(-t * slide_distance / duration * 0.1), 'center'))
    return clip

def load_clip(asset, start, duration, effect, target_height, target_width):
    try:
        offset = asset.get('offset', {'x': 0.5, 'y': 0.5})  # Default to center if not specified
        if asset['type'] == 'image':
            clip = ImageClip(asset['src'], duration=duration or 0.1).resize(height=target_height)
            
            # Calculate position based on offset values
            x_pos = int((offset['x'] * target_width) - (clip.w / 2))
            y_pos = int((offset['y'] * target_height) - (clip.h / 2))

            # Apply the calculated position to the clip
            clip = clip.set_position((x_pos, y_pos))
            clip = apply_effects(clip, effect, duration or 0.1)
            clip = clip.set_start(start).set_duration(duration or 0.1)
            return clip, 'video'
        elif asset['type'] == 'audio':
            audio = AudioFileClip(asset['src']).set_start(start).fx(afx.audio_normalize)
            if duration:
                audio = audio.set_duration(duration).volumex(asset.get('volume', 1.0))
            return audio, 'audio'
    except Exception as e:
        print(f"Error loading asset: {asset['src']} - {str(e)}")
    return None, None

def process_video_clips(tracks, target_height, target_width):
    video_clips = []
    for track in tracks:
        for clip_data in track['clips']:
            clip, clip_type = load_clip(
                clip_data['asset'],
                clip_data['start'],
                clip_data['length'],
                clip_data.get('effect', ''),
                target_height,
                target_width
            )
            if clip_type == 'video':
                video_clips.append(clip)
    return video_clips

def process_audio_clips(tracks):
    audio_clips = []
    for track in tracks:
        for clip_data in track['clips']:
            clip, clip_type = load_clip(
                clip_data['asset'],
                clip_data['start'],
                clip_data['length'],
                clip_data.get('effect', ''),
                0,  # Height is irrelevant for audio
                0   # Width is irrelevant for audio
            )
            if clip_type == 'audio':
                audio_clips.append(clip)
    return audio_clips

def combine_clips(video_clips, audio_clips, target_width, target_height):
    final_clip = CompositeVideoClip(video_clips, size=(target_width, target_height))
    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips)
        fade_duration = min(0.5, final_audio.duration / 10)
        final_audio = final_audio.fx(afx.audio_fadein, fade_duration).fx(afx.audio_fadeout, fade_duration)
        final_audio = final_audio.set_duration(final_clip.duration)
        final_clip = final_clip.set_audio(final_audio)
    final_clip = final_clip.set_duration(max(final_clip.duration, final_audio.duration if audio_clips else 0))
    return final_clip

def write_output(final_clip, file_name):
    # Ensure the file_name ends with .mp4
    if not file_name.endswith(".mp4"):
        file_name += ".mp4"
        
    final_clip.write_videofile(
        file_name,
        codec="libx264",
        audio_codec="aac",
        fps=30,
        audio=True,
        threads=4
    )

def create_video_from_json(json_data, file_name):
    output_size = json_data['output']['size']
    target_width = output_size['width']
    target_height = output_size['height']
    tracks = json_data['timeline']['tracks']

    video_clips = process_video_clips(tracks, target_height, target_width)
    audio_clips = process_audio_clips(tracks)

    final_clip = combine_clips(video_clips, audio_clips, target_width, target_height)
    write_output(final_clip, file_name)

    return {"status": "success", "video_url": file_name}


# # Load and process the JSON data
# json_data = load_json('./example.json')
# response = create_video_from_json(json_data)
# print(response)
