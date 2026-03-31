
import sys
import os

# Adiciona o diretorio atual ao sys.path para importar o app
sys.path.append(os.getcwd())

from app.services.youtube_review_consensus import YoutubeReviewConsensusService
from app.services.youtube_video_sources import YoutubeVideoDetail, YoutubeVideoChapter
from app.services.youtube_video_ocr import FfmpegRapidOcrYoutubeVideoOcrProvider

def test_ocr_extraction():
    # URL de um video que sabemos que tem benchmarks (do seu log do curl)
    # RTX 4080 Super + Ryzen 5 9600x
    video_url = "https://www.youtube.com/watch?v=Utvf9hzJa-I"
    
    # Vamos simular apenas um capitulo para ser rapido
    detail = YoutubeVideoDetail(
        title="RTX 4080 Super + Ryzen 5 9600x",
        url=video_url,
        channel="Test",
        description="Benchmark test",
        transcript="",
        chapters=(
            # Forcando um ponto diferente para ver se pegamos padroes variados
            YoutubeVideoChapter(title="Cyberpunk 2077 Benchmark", start_time=140.0, end_time=160.0),
        )
    )

    # Precisamos do stream_url para o ffmpeg. 
    # O YoutubeReviewConsensusService normalmente pega isso via ytdlp.
    # Para este teste manual, vamos instanciar o provedor de OCR diretamente.
    
    print("Iniciando busca de stream_url via yt-dlp...")
    service = YoutubeReviewConsensusService()
    try:
        real_detail = service.video_detail_provider.fetch(url=video_url, fallback_title="Test", fallback_channel="Test")
        detail = real_detail
    except Exception as e:
        print(f"Erro ao buscar detalhes: {e}")
        return

    if not detail.stream_url:
        print("Nao foi possivel obter o stream_url do video.")
        return

    print(f"Stream URL obtido. Analisando capitulo: {detail.chapters[0].title if detail.chapters else 'N/A'}")
    
    ocr_provider = FfmpegRapidOcrYoutubeVideoOcrProvider(frame_limit=1, frames_per_chapter=1)
    observations = ocr_provider.analyze(detail)
    
    print("\n--- OCR Observations ---")
    for obs in observations:
        print(obs)
        print("-" * 20)

if __name__ == "__main__":
    test_ocr_extraction()
