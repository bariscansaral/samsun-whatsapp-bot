import os
import sys
import json
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

# Arayüz tema ayarları
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

CONFIG_DOSYASI = "config.json"

# Varsayılan kelime listeleri ve ayarlar
VARSAYILAN_CONFIG = {
    "debug_modu": False,
    "otomatik_gonder": False,
    "yanit_mesaji": "ben yardımcı olabilirim",
    "samsun_lokasyonlari": [
        "samsun", "smsun", "samusn", "samsn", "ilkadım", "ilkadim", "ilkadm", "ılkadm",
        "atakum", "atalum", "atkum", "atakm", "canik", "cank", "canık",
        "çarşamba", "carsamba", "carsmaba", "çarşamb", "carsamb", "bafra", "bafta", "bafr",
        "tekkeköy", "tekkekoy", "tekkeky", "tekeköy", "tekekoy", "kavak", "ondokuzmayıs",
        "ondokuzmayis", "19 mayıs", "19 mayis", "omü", "omu"
    ],
    "haric_lokasyonlar": [
        "alaçam", "alacam", "alacm", "alaçm", "ladik", "ladk", "vezirköprü", "vezirkopru",
        "havza", "terme", "asarcık", "asarcik", "ayvacık", "ayvacik", "salıpazarı", "salipazari", "yakakent"
    ],
    "hukuki_islemler": [
        "arabulucu", "arabuluculuk", "duruşma", "durusma", "dava", "haciz", "hacze", "hacz",
        "keşif", "kesif", "adliye", "adlye", "mahkeme", "icra", "icr", "hukuk", "ceza",
        "sulh", "asliye", "tevkil", "tvkil", "yetki belgesi", "yetki", "vekalet", "dosya",
        "kalem", "fotokopi", "masraf", "müzekkere", "muzekkere", "savcılık", "savcilik",
        "ifade", "tapu", "vergi dairesi", "belediye", "ön büro", "önbüro", "müvekkil",
        "muvekkil", "savcı", "savci", "görüşme", "gorusme", "evrak", "teminat mektubu", "bam"
    ],
    "talep_ifadeleri": [
        "var mı", "var mi", "varmı", "varmi", "varm", "varmıdır", "var mıdır",
        "gidebilecek", "gidicek", "gidecek", "katılabilecek", "katilabilecek", "katılacak",
        "bakabilecek", "bakacak", "yapabilecek", "yapacak", "alabilecek", "alacak",
        "yardımcı olabilecek", "yardımcı olabilir misiniz", "yardımcı olacak",
        "kim var", "kimse var mı", "ariyorum", "ariyoruz", "arıyorum", "arıyoruz",
        "ihtiyac", "ihtiyaç", "ihtiyacımız", "ihtiyaçımız", "lazım", "lazim",
        "rica etsem", "bulabilir miyiz", "arayışımız var"
    ],
    "genel_meslektas_arama": [
        "avukat", "meslektaş", "meslektas", "mslektas", "mslektaş", "avukt", "avkat", "meslektaş var"
    ]
}


def config_yukle():
    if os.path.exists(CONFIG_DOSYASI):
        try:
            with open(CONFIG_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return VARSAYILAN_CONFIG


def config_kaydet(veri):
    try:
        with open(CONFIG_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        return False


class TevkilBotGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        try:
            self.iconbitmap("elephant.ico")
        except Exception:
            pass

        self.title("Samsun Tevkil Botu - Kontrol Merkezi")
        self.geometry("1000, 700")
        self.minsize(900, 600)

        self.config_data = config_yukle()
        self.bot_process = None

        # Ana Yerleşim (Tabview)
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=15)

        self.tab_kontrol = self.tabview.add("📊 Kontrol & Loglar")
        self.tab_ayarlar = self.tabview.add("⚙️ Bot Ayarları")
        self.tab_kelimeler = self.tabview.add("📝 Kelime Filtreleri")

        self.setup_kontrol_tab()
        self.setup_ayarlar_tab()
        self.setup_kelimeler_tab()

    # ==========================================================
    # 1. SEKME: KONTROL & LOGLAR
    # ==========================================================
    def setup_kontrol_tab(self):
        self.tab_kontrol.grid_columnconfigure(0, weight=1)
        self.tab_kontrol.grid_rowconfigure(1, weight=1)

        # Üst Butonlar ve Durum Çerçevesi
        top_frame = ctk.CTkFrame(self.tab_kontrol, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        self.btn_baslat = ctk.CTkButton(
            top_frame, text="▶ Botu Başlat", fg_color="#10b981", hover_color="#059669",
            font=("Arial", 14, "bold"), width=150, height=40, command=self.botu_baslat
        )
        self.btn_baslat.pack(side="left", padx=5)

        self.btn_durdur = ctk.CTkButton(
            top_frame, text="⏹ Botu Durdur", fg_color="#ef4444", hover_color="#dc2626",
            font=("Arial", 14, "bold"), width=150, height=40, state="disabled", command=self.botu_durdur
        )
        self.btn_durdur.pack(side="left", padx=5)

        btn_temizle = ctk.CTkButton(
            top_frame, text="🧹 Ekranı Temizle", fg_color="#64748b", hover_color="#475569",
            font=("Arial", 13, "bold"), width=130, height=40, command=self.ekrani_temizle
        )
        btn_temizle.pack(side="left", padx=15)

        self.lbl_durum = ctk.CTkLabel(
            top_frame, text="Durum: Bekliyor 🔴", font=("Arial", 13, "bold"), text_color="#9ca3af"
        )
        self.lbl_durum.pack(side="right", padx=10)

        # Log Konsol Ekranı
        log_frame = ctk.CTkFrame(self.tab_kontrol)
        log_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=10)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

        self.log_konsol = ctk.CTkTextbox(log_frame, font=("Consolas", 12), text_color="#38bdf8", fg_color="#09090b")
        self.log_konsol.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.log_konsol.configure(state="disabled")

    # ==========================================================
    # 2. SEKME: BOT AYARLARI
    # ==========================================================
    def setup_ayarlar_tab(self):
        self.tab_ayarlar.grid_columnconfigure(0, weight=1)

        frame = ctk.CTkFrame(self.tab_ayarlar)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Debug Modu
        self.switch_debug = ctk.CTkSwitch(
            frame, text="Debug Modu (Kendi mesajlarına da yanıt verir - Test için)", font=("Arial", 13)
        )
        self.switch_debug.pack(anchor="w", padx=20, pady=15)
        if self.config_data.get("debug_modu"):
            self.switch_debug.select()

        # Otomatik Gönderim
        self.switch_gonder = ctk.CTkSwitch(
            frame, text="Otomatik Gönderim (Açıkse mesaj atar, kapalıysa sadece simülasyon/log)", font=("Arial", 13)
        )
        self.switch_gonder.pack(anchor="w", padx=20, pady=15)
        if self.config_data.get("otomatik_gonder"):
            self.switch_gonder.select()

        # Yanıt Mesajı
        lbl_yanit = ctk.CTkLabel(frame, text="Özel Yanıt Mesajı:", font=("Arial", 13, "bold"))
        lbl_yanit.pack(anchor="w", padx=20, pady=(15, 5))

        self.entry_yanit = ctk.CTkEntry(frame, width=400, font=("Arial", 13))
        self.entry_yanit.pack(anchor="w", padx=20, pady=5)
        self.entry_yanit.insert(0, self.config_data.get("yanit_mesaji", "ben yardımcı olabilirim"))

        # Kaydet Butonu
        btn_kaydet = ctk.CTkButton(
            frame, text="Ayarları Kaydet", font=("Arial", 13, "bold"), fg_color="#3b82f6", hover_color="#2563eb",
            command=self.ayarlari_kaydet
        )
        btn_kaydet.pack(anchor="w", padx=20, pady=30)

    # ==========================================================
    # 3. SEKME: KELİME FİLTRELERİ
    # ==========================================================
    def setup_kelimeler_tab(self):
        self.tab_kelimeler.grid_columnconfigure((0, 1), weight=1)
        self.tab_kelimeler.grid_rowconfigure((0, 1), weight=1)

        # Yardımcı metin
        lbl_bilgi = ctk.CTkLabel(
            self.tab_kelimeler, text="Kelimeleri virgülle veya alt alta yazarak düzenleyebilirsiniz.",
            font=("Arial", 12), text_color="#9ca3af"
        )
        lbl_bilgi.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 0))

        # 1. Samsun Lokasyonları
        f1 = ctk.CTkFrame(self.tab_kelimeler)
        f1.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(f1, text="Samsun Lokasyonları", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=5)
        self.txt_samsun = ctk.CTkTextbox(f1, height=120)
        self.txt_samsun.pack(fill="both", expand=True, padx=10, pady=5)
        self.txt_samsun.insert("1.0", ", ".join(self.config_data.get("samsun_lokasyonlari", [])))

        # 2. Hariç Tutulanlar (Kara Liste)
        f2 = ctk.CTkFrame(self.tab_kelimeler)
        f2.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(f2, text="Hariç Tutulacak Yerler (Kara Liste)", font=("Arial", 12, "bold")).pack(anchor="w",
                                                                                                      padx=10, pady=5)
        self.txt_haric = ctk.CTkTextbox(f2, height=120)
        self.txt_haric.pack(fill="both", expand=True, padx=10, pady=5)
        self.txt_haric.insert("1.0", ", ".join(self.config_data.get("haric_lokasyonlar", [])))

        # 3. Hukuki İşlemler
        f3 = ctk.CTkFrame(self.tab_kelimeler)
        f3.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(f3, text="Hukuki İşlemler", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=5)
        self.txt_hukuki = ctk.CTkTextbox(f3, height=120)
        self.txt_hukuki.pack(fill="both", expand=True, padx=10, pady=5)
        self.txt_hukuki.insert("1.0", ", ".join(self.config_data.get("hukuki_islemler", [])))

        # 4. Talep İfadeleri
        f4 = ctk.CTkFrame(self.tab_kelimeler)
        f4.grid(row=2, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(f4, text="Talep İfadeleri", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=5)
        self.txt_talep = ctk.CTkTextbox(f4, height=120)
        self.txt_talep.pack(fill="both", expand=True, padx=10, pady=5)
        self.txt_talep.insert("1.0", ", ".join(self.config_data.get("talep_ifadeleri", [])))

        # Kelimeleri Kaydet Tuşu
        btn_kelime_kaydet = ctk.CTkButton(
            self.tab_kelimeler, text="Kelime Listelerini Kaydet", font=("Arial", 13, "bold"), fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self.kelimeleri_kaydet
        )
        btn_kelime_kaydet.grid(row=3, column=0, columnspan=2, pady=15)

    # ==========================================================
    # İŞLEVSEL METOTLAR
    # ==========================================================
    def ayarlari_kaydet(self):
        self.config_data["debug_modu"] = True if self.switch_debug.get() == 1 else False
        self.config_data["otomatik_gonder"] = True if self.switch_gonder.get() == 1 else False
        self.config_data["yanit_mesaji"] = self.entry_yanit.get().strip()

        if config_kaydet(self.config_data):
            messagebox.showinfo("Başarılı", "Bot ayarları başarıyla kaydedildi!")
        else:
            messagebox.showerror("Hata", "Ayarlar kaydedilirken bir hata oluştu.")

    def kelimeleri_kaydet(self):
        def parse_text(text_widget):
            raw = text_widget.get("1.0", "end").strip()
            # Virgülle veya satır başlarıyla ayırıp temizle
            items = [i.strip().lower() for i in raw.replace("\n", ",").split(",") if i.strip()]
            return list(set(items))  # Tekrarları önle

        self.config_data["samsun_lokasyonlari"] = parse_text(self.txt_samsun)
        self.config_data["haric_lokasyonlar"] = parse_text(self.txt_haric)
        self.config_data["hukuki_islemler"] = parse_text(self.txt_hukuki)
        self.config_data["talep_ifadeleri"] = parse_text(self.txt_talep)

        if config_kaydet(self.config_data):
            messagebox.showinfo("Başarılı", "Kelime filtreleri başarıyla güncellendi!")
        else:
            messagebox.showerror("Hata", "Kelimeler kaydedilirken bir hata oluştu.")

    def log_yaz(self, mesaj):
        self.log_konsol.configure(state="normal")


        satir_sayisi = int(self.log_konsol.index('end-1c').split('.')[0])
        if satir_sayisi > 300:
            self.log_konsol.delete("1.0", "100.0")
        # ----------------------------------------

        self.log_konsol.insert("end", mesaj + "\n")
        self.log_konsol.see("end")
        self.log_konsol.configure(state="disabled")

    def ekrani_temizle(self):
        self.log_konsol.configure(state="normal")
        self.log_konsol.delete("1.0", "end")
        self.log_konsol.configure(state="disabled")

    def botu_baslat(self):
        # Eğer bot zaten çalışıyorsa tekrar başlatma
        if hasattr(self, 'bot_thread') and self.bot_thread and self.bot_thread.is_alive():
            messagebox.showwarning("Uyarı", "Bot zaten çalışıyor!")
            return

        # Başlatmadan önce güncel ayarları JSON'a yaz
        self.ayarlari_kaydet()

        # Çevre değişkenlerini ayarla (bot.py burayı okuyabilir)
        os.environ["DEBUG_MODU"] = "True" if self.config_data["debug_modu"] else "False"
        os.environ["OTOMATIK_GONDER"] = "True" if self.config_data["otomatik_gonder"] else "False"
        os.environ["YANIT_MESAJI"] = self.config_data["yanit_mesaji"]

        try:
            # bot.py modülünü proje içinden çağırıyoruz
            import bot

            # Global durdurma bayrağını sıfırla (bot.py içinde kontrol edilebilir)
            if hasattr(bot, "DURDURMA_BAYRAGI"):
                bot.DURDURMA_BAYRAGI = False

            # Arayüzü dondurmamak için botu arka plan thread'ine veriyoruz
            self.bot_thread = threading.Thread(target=self.botu_arkada_calistir, daemon=True)
            self.bot_thread.start()

            self.btn_baslat.configure(state="disabled")
            self.btn_durdur.configure(state="normal")
            self.lbl_durum.configure(text="Durum: Çalışıyor 🟢", text_color="#10b981")
            self.log_yaz(">>> Bot arka planda başlatıldı...")

        except Exception as e:
            messagebox.showerror("Hata", f"Bot başlatılamadı: {e}")

    def botu_arkada_calistir(self):
        class StdoutRedirector:
            def __init__(self, log_fonksiyonu):
                self.log_fonksiyonu = log_fonksiyonu

            def write(self, text):
                if text.strip():
                    self.log_fonksiyonu(text.strip())

            def flush(self):
                pass

        old_stdout = sys.stdout
        sys.stdout = StdoutRedirector(self.log_yaz)

        try:
            import runpy
            # bot.py dosyasını ayrı bir pencere açmadan, doğrudan bu thread içinde çalıştırır
            runpy.run_path("bot.py", run_name="__main__")
        except Exception as e:
            self.log_yaz(f">>> Bot hata ile durdu: {e}")
        finally:
            sys.stdout = old_stdout
            try:
                self.lbl_durum.configure(text="Durum: Durduruldu 🔴", text_color="#9ca3af")
                self.btn_baslat.configure(state="normal")
                self.btn_durdur.configure(state="disabled")
                self.log_yaz(">>> Bot sonlandırıldı.")
            except:
                pass

    def bot_cikti_oku(self):
        while self.bot_process and self.bot_process.poll() is None:
            line = self.bot_process.stdout.readline()
            if line:
                self.log_yaz(line.strip())

        self.lbl_durum.configure(text="Durum: Durduruldu 🔴", text_color="#9ca3af")
        self.btn_baslat.configure(state="normal")
        self.btn_durdur.configure(state="disabled")
        self.log_yaz(">>> Bot sonlandırıldı.")

    def botu_durdur(self):
        try:
            import bot
            if hasattr(bot, "DURDURMA_BAYRAGI"):
                bot.DURDURMA_BAYRAGI = True
        except:
            pass

        self.log_yaz(">>> Bot durduruluyor...")
        self.lbl_durum.configure(text="Durum: Durduruldu 🔴", text_color="#9ca3af")
        self.btn_baslat.configure(state="normal")
        self.btn_durdur.configure(state="disabled")


if __name__ == "__main__":
    app = TevkilBotGUI()
    app.mainloop()