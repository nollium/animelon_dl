import ffmpeg
(
    ffmpeg
    .input("input.mp4")
    .filter("subtitles", "subtitles.ass")
    .output("output.mp4")
    .run()
)