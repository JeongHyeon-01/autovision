import json
import ffmpeg

# 추후 post시 json으로 받아옴
def load_json(file_path: str):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def create_video_from_json(json_data):
    video_clips = []
    audio_clips = []

    # JSON에서 해상도 설정 읽기
    output_size = json_data['output']['size']
    target_width = output_size['width']
    target_height = output_size['height']

    # 모든 입력 클립에 대해 일관된 SAR 설정
    target_sar = '1/1'  # SAR을 1/1로 설정

    # 전체 비디오 길이를 저장할 변수
    total_duration = 0

    # Extract clips from tracks
    for track in json_data['timeline']['tracks']:
        for clip in track['clips']:
            if clip['asset']['type'] == 'image':
                # 이미지 클립의 경우, 해상도를 확인하고 변환
                input_clip = ffmpeg.input(clip['asset']['src'])

                # 원본 해상도를 가져오는 방법
                probe = ffmpeg.probe(clip['asset']['src'])
                video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                if video_stream:
                    width = int(video_stream['width'])
                    height = int(video_stream['height'])

                    # 이미지의 비율에 따라 스케일 조정 및 패딩
                    if width != target_width or height != target_height:
                        input_clip = input_clip.filter('scale', target_width, target_height).filter('pad', target_width, target_height, '(ow-iw)/2', '(oh-ih)/2', color='black')

                # SAR 설정 및 FPS, 포맷 설정
                input_clip = input_clip.filter('setsar', sar=target_sar)  # SAR을 1/1로 설정
                input_clip = input_clip.filter('fps', fps=25, round='up')  # FPS 설정
                input_clip = input_clip.filter('format', 'yuv420p')  # 픽셀 형식 변환 추가

                # 이미지가 원하는 길이만큼 유지되도록 설정
                input_clip = input_clip.filter('tpad', stop_mode='clone', stop_duration=clip['length'])

                # 빈 공간을 추가하여 클립의 시작 시간을 맞춤
                if clip['start'] > total_duration:
                    # 이전 클립과 다음 클립 사이의 빈 공간을 검정색 화면으로 채움
                    null_duration = clip['start'] - total_duration
                    null_clip = ffmpeg.input('color=c=black:s={}x{}'.format(target_width, target_height), f='lavfi', t=null_duration)
                    null_clip = null_clip.filter('setsar', sar=target_sar)  # SAR을 1/1로 설정
                    video_clips.append(null_clip)

                # 이미지 클립을 비디오 클립 목록에 추가
                video_clips.append(input_clip)

                # 비디오의 총 길이 업데이트
                total_duration = clip['start'] + clip['length']

            elif clip['asset']['type'] == 'audio':
                # 오디오 클립을 입력으로 가져옴
                input_audio = ffmpeg.input(clip['asset']['src'], t=total_duration)

                # 오디오의 시작 부분을 맞추기 위한 null 오디오
                if clip['start'] > 0:
                    silent_audio = ffmpeg.input('anullsrc=r=44100:cl=stereo', f='lavfi', t=clip['start'])
                    audio_clips.append(silent_audio)

                # 오디오의 지속 시간 설정 및 패딩
                input_audio = input_audio.filter('atrim', duration=clip['length'])  # 오디오 클립을 length만큼 자름
                input_audio = input_audio.filter('apad', whole_dur=clip['length'])  # 오디오가 length에 맞도록 패딩

                # 오디오 포맷 설정
                input_audio = input_audio.filter('aformat', sample_fmts='s16')  
                audio_clips.append(input_audio)

    # Combine video clips using ffmpeg
    if video_clips:
        output_file = "output_video.mp4"
        # 비디오 스트림 생성
        video_stream = ffmpeg.concat(*video_clips, v=1, a=0)
        
        # 오디오 스트림이 있는 경우 결합
        if audio_clips:
            audio_stream = ffmpeg.concat(*audio_clips, v=0, a=1)
            output = ffmpeg.output(video_stream, audio_stream, output_file, t=total_duration ,vcodec='libx264', acodec='aac', s='{}x{}'.format(target_width, target_height))
        else:
            output = ffmpeg.output(video_stream, output_file, vcodec='libx264', s='{}x{}'.format(target_width, target_height))

        # 실행
        output.run(overwrite_output=True)
        
        return {"status": "success", "video_url": output_file}
    else:
        return {"status": "error", "message": "No clips found to process"}




json_data = load_json('./example.json')
response = create_video_from_json(json_data)

