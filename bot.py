import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
import subprocess
import re
import os
import threading
import shutil


class AudioTrimmerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎵 faySound | Ses Boşlukları Temizle")
        self.root.geometry("500x200")
        self.root.resizable(False, False)
        main_frame = ttk.Frame(root, padding=20)
        main_frame.pack(expand=True, fill="both")
        self.select_button = ttk.Button(
            main_frame, text="🎵 Ses Dosyası Seç", command=self.select_file
        )
        self.select_button.pack(pady=10, fill="x")
        self.file_label = ttk.Label(
            main_frame, text="⚠ Dosya seçilmedi", font=("Arial", 10)
        )
        self.file_label.pack(pady=5)
        self.process_button = ttk.Button(
            main_frame, text="✂ Sesi İşle", command=self.start_processing
        )
        self.process_button.pack(pady=15, fill="x")
        self.progress_label = ttk.Label(
            main_frame, text="🔄 İşlem Durumu: Bekleniyor...", font=("Arial", 10)
        )
        self.progress_label.pack(pady=5)
        self.progress_bar = ttk.Progressbar(main_frame, length=250, mode="determinate")
        self.progress_bar.pack(pady=5)
        self.status_label = ttk.Label(
            main_frame, text="", font=("Arial", 10), foreground="red"
        )
        self.status_label.pack(pady=5)
        self.input_file = None
        self.temp_dir = os.path.abspath("temp_audio")
        self.ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe")

    def select_file(self):
        self.input_file = filedialog.askopenfilename(
            filetypes=[("MP3 Dosyaları", "*.mp3")]
        )
        if self.input_file:
            self.file_label.config(
                text=f"✅ Seçili dosya: {os.path.basename(self.input_file)}",
                foreground="green",
            )

    def get_audio_duration(self, input_file):
        """FFmpeg ile ses dosyasının toplam süresini öğrenir."""
        cmd = [self.ffmpeg_path, "-i", input_file, "-hide_banner", "-f", "null", "-"]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        if match:
            hours, minutes, seconds = map(float, match.groups())
            return hours * 3600 + minutes * 60 + seconds
        return None

    def detect_silence(self, input_file):
        """Sessizlik zamanlarını FFmpeg ile belirler."""
        cmd = [
            self.ffmpeg_path,
            "-i",
            input_file,
            "-af",
            "silencedetect=noise=-40dB:d=0.5",
            "-f",
            "null",
            "-",
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, check=True)
        silence_timestamps = []
        for line in result.stderr.split("\n"):
            if "silence_start" in line or "silence_end" in line:
                match = re.search(r"silence_(start|end): ([0-9]+\.[0-9]+)", line)
                if match:
                    silence_timestamps.append(float(match.group(2)))
        return silence_timestamps

    def process_audio(self):
        if not self.input_file:
            self.status_label.config(
                text="🚨 Lütfen önce bir dosya seçin!", foreground="red"
            )
            return
        try:
            self.status_label.config(
                text="⏳ Sessizlikler analiz ediliyor...", foreground="orange"
            )
            self.progress_label.config(
                text="🔄 İşlem Durumu: Sessizlikleri Analiz Ediyor..."
            )
            self.progress_bar["value"] = 0
            self.root.update()

            silence_times = self.detect_silence(self.input_file)
            if not silence_times:
                self.status_label.config(
                    text="⚠ Hiç sessizlik bulunamadı!", foreground="red"
                )
                return

            audio_duration = self.get_audio_duration(self.input_file)

            segments = []
            last_end = 0.0
            for i in range(0, len(silence_times), 2):
                if i + 1 < len(silence_times):
                    silence_start = silence_times[i]
                    silence_end = silence_times[i + 1]
                    segments.append((last_end, silence_start))
                    last_end = silence_end

            if audio_duration and last_end < audio_duration:
                segments.append((last_end, audio_duration))

            self.status_label.config(
                text="✂ Ses kesiliyor, lütfen bekleyin...", foreground="blue"
            )
            self.progress_label.config(text="🔄 İşlem Durumu: Ses Kesiliyor...")
            self.root.update()

            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            os.makedirs(self.temp_dir)

            temp_segments = []
            segment_count = len(segments)
            for i, (start, end) in enumerate(segments):
                temp_filename = os.path.join(self.temp_dir, f"segment_{i}.wav")
                temp_segments.append(temp_filename)
                if end:
                    subprocess.run(
                        [
                            self.ffmpeg_path,
                            "-i",
                            self.input_file,
                            "-fflags",
                            "+genpts",
                            "-ss",
                            str(start),
                            "-to",
                            str(end),
                            "-ar",
                            "44100",
                            "-ac",
                            "2",
                            "-c:a",
                            "pcm_s16le",
                            temp_filename,
                        ],
                        check=True,
                    )
                self.progress_bar["value"] = (i + 1) / segment_count * 50
                self.root.update()

            self.progress_label.config(text="🔄 İşlem Durumu: Ses Birleştiriliyor...")
            self.progress_bar["value"] = 75
            self.root.update()

            temp_output = os.path.join(self.temp_dir, "final_audio.mp3")
            file_list_path = os.path.join(self.temp_dir, "file_list.txt")
            with open(file_list_path, "w", encoding="utf-8") as f:
                for temp_file in temp_segments:
                    f.write(f"file '{os.path.abspath(temp_file)}'\n")

            subprocess.run(
                [
                    self.ffmpeg_path,
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    file_list_path,
                    "-c:a",
                    "libmp3lame",
                    "-q:a",
                    "2",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    temp_output,
                ],
                check=True,
            )

            while not os.path.exists(temp_output) or os.path.getsize(temp_output) == 0:
                self.root.update()

            self.progress_label.config(text="✅ İşlem Tamamlandı!")
            self.progress_bar["value"] = 100
            self.status_label.config(text="✅ İşlem tamamlandı!", foreground="green")

            output_file = filedialog.asksaveasfilename(
                defaultextension=".mp3",
                filetypes=[("MP3 Dosyası", "*.mp3")],
                initialfile="faysound-temizlenmis.mp3",
            )
            if output_file:
                shutil.move(temp_output, output_file)
                self.status_label.config(
                    text="🎉 Dosya başarıyla kaydedildi!", foreground="green"
                )
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            self.status_label.config(text=f"🚨 Hata oluştu: {str(e)}", foreground="red")

    def start_processing(self):
        processing_thread = threading.Thread(target=self.process_audio)
        processing_thread.start()


if __name__ == "__main__":
    root = tk.Tk()
    app = AudioTrimmerApp(root)
    root.mainloop()
