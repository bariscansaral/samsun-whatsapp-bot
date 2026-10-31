import os
import random
import re
import sys
import time
import json
import logging
from logging.handlers import TimedRotatingFileHandler
from collections import deque
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    NoSuchWindowException,
    InvalidSessionIdException,
    StaleElementReferenceException,
    WebDriverException,
)

# ============================================================
# MERKEZI LOGLAMA
# ============================================================

LOG_DIZINI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "logs"
)

SOHBET_LOG_DIZINI = os.path.join(LOG_DIZINI, "chats")
os.makedirs(SOHBET_LOG_DIZINI, exist_ok=True)

SYSTEM_LOG_DOSYASI = os.path.join(LOG_DIZINI, "system.log")
SELENIUM_LOG_DOSYASI = os.path.join(LOG_DIZINI, "selenium.log")

DEBUG_ALINTI_LOG_DOSYASI = os.path.join(LOG_DIZINI, "debug_alinti.log")

LOG_FORMATI = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def logger_olustur(ad, dosya_yolu, seviye=logging.INFO):
    """Belirtilen dosyaya yazan, günlük döndüren logger oluşturur."""
    lg = logging.getLogger(ad)
    lg.setLevel(seviye)
    lg.propagate = False

    # Aynı dosyaya birden fazla handler eklenmesini önle.
    if not any(
        getattr(h, "baseFilename", None)
        == os.path.abspath(dosya_yolu)
        for h in lg.handlers
    ):
        handler = TimedRotatingFileHandler(
            dosya_yolu,
            when="midnight",
            interval=1,
            backupCount=14,
            encoding="utf-8",
            delay=False
        )
        handler.suffix = "%Y-%m-%d"
        handler.setFormatter(LOG_FORMATI)
        lg.addHandler(handler)

    return lg


logger = logger_olustur(
    "whatsapp_bot.system",
    SYSTEM_LOG_DOSYASI
)

selenium_logger = logger_olustur(
    "whatsapp_bot.selenium",
    SELENIUM_LOG_DOSYASI,
    logging.DEBUG
)

alinti_debug_logger = logger_olustur(
    "whatsapp_bot.alinti_debug",
    DEBUG_ALINTI_LOG_DOSYASI,
    logging.DEBUG
)

# Selenium kütüphanesinin loglarını mevcut Selenium logger'ına yönlendir.
selenium_kutuphane_logger = logging.getLogger("selenium")
selenium_kutuphane_logger.setLevel(logging.WARNING)
selenium_kutuphane_logger.propagate = False

for handler in list(selenium_kutuphane_logger.handlers):
    selenium_kutuphane_logger.removeHandler(handler)
    handler.close()

for handler in selenium_logger.handlers:
    selenium_kutuphane_logger.addHandler(handler)

if not any(
    getattr(h, "baseFilename", None)
    == os.path.abspath(SELENIUM_LOG_DOSYASI)
    for h in selenium_kutuphane_logger.handlers
):
    selenium_handler = TimedRotatingFileHandler(
        SELENIUM_LOG_DOSYASI,
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
        delay=False
    )
    selenium_handler.suffix = "%Y-%m-%d"
    selenium_handler.setFormatter(LOG_FORMATI)
    selenium_kutuphane_logger.addHandler(selenium_handler)

# Log dosyalarının ve klasörün yolunu başlangıçta göster.
print(f"[LOG] Klasör: {LOG_DIZINI}")
print(f"[LOG] Sistem: {SYSTEM_LOG_DOSYASI}")
print(f"[LOG] Selenium: {SELENIUM_LOG_DOSYASI}")


# ==================================================
# AYARLAR
# ==================================================



YANIT_MESAJI = os.environ.get("YANIT_MESAJI", "ben yardımcı olabilirim")

DEBUG_MODU = os.environ.get("DEBUG_MODU", "False") == "True"            # True ise: Kendi mesajlarına da yanıt verir (Test modu)
                                                                        # False ise: Canlı mod, kendi giden mesajlarını otomatik eler
OTOMATIK_GONDER = os.environ.get("OTOMATIK_GONDER", "False") == "True"  # Simülasyon: False ise Hiçbir şekilde mesaj atmaz, alıntı yapmaz sadece loglama yapar test için

print(
    f"[AYAR] Debug Modu: {DEBUG_MODU} | Otomatik Gönderim: {OTOMATIK_GONDER}| Yanıt Mesajı: '{YANIT_MESAJI}'"
)

# Debug modundaysak kendi mesajlarımızı işle, canlı moddaysak yok say
KENDI_MESAJLARIMI_ISLE = True if DEBUG_MODU else False

ALINTI_TEKRAR_BEKLEME = 3.0
ALINTI_MAKSIMUM_DENEME = 3

KONTROL_ARALIGI = 0.5
HAFIZA_BOYUTU = 1000

CONFIG_DOSYASI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "config.json")

# ==================================================
# KELİME FİLTRELESİ
# ==================================================

def config_oku():
    """Arayüzden (gui.py) kaydedilen config.json dosyasını okur."""
    varsayilanlar = {
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

    if os.path.exists(CONFIG_DOSYASI):
        try:
            with open(CONFIG_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return varsayilanlar

# Dinamik listeleri config'den çekiyoruz
_cfg = config_oku()

SAMSUN_LOKASYONLARI = _cfg.get("samsun_lokasyonlari", [])
HARIC_LOKASYONLAR = _cfg.get("haric_lokasyonlar", [])
HUKUKI_ISLEMLER = _cfg.get("hukuki_islemler", [])
TALEP_IFADELERI = _cfg.get("talep_ifadeleri", [])
GENEL_MESLEKTAS_ARAMA = _cfg.get("genel_meslektas_arama", [])

TURKIYE_ILLERI = [
    "adana", "adıyaman", "afyonkarahisar", "ağrı", "aksaray", "amasya", "ankara", "antalya", "ardahan","artvin", "aydın", "balıkesir",
    "bartın", "batman", "bayburt", "bilecik", "bingöl", "bitlis", "bolu", "burdur", "bursa", "çanakkale", "çankırı", "çorum",
    "denizli", "diyarbakır", "düzce", "elazığ", "erzincan", "erzurum", "eskişehir", "gaziantep", "giresun", "gümüşhane", "hakkari",
    "hatay", "ığdır", "ısparta", "istanbul", "izmir", "kahramanmaraş", "karabük", "karaman", "kars", "kastamonu", "kayseri",
    "kırıkkale", "kırklareli", "kırşehir","kilis", "kocaeli", "konya", "kütahya", "malatya", "manisa", "mardin", "mersin",
    "muğla", "muş", "nevşehir", "niğde", "ordu", "osmaniye", "rize", "sakarya", "samsun","siirt", "sinop", "sivas", "şanlıurfa",
    "şırnak", "tekirdağ", "tokat", "trabzon", "tunceli", "uşak", "van", "yalova", "yozgat", "zonguldak",
]

# ==================================================
# YARDIMCI VE FİLTRE FONKSİYONLARI
# ==================================================

def turkce_kucuk(metin):
    metin = str(metin or "")
    metin = metin.replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"\s+", " ", metin).strip()

def konum_anahtari(metin):
    metin = turkce_kucuk(metin)
    ceviri = str.maketrans({
        "ı": "i",
        "ş": "s",
        "ğ": "g",
        "ü": "u",
        "ö": "o",
        "ç": "c",
    })
    return metin.translate(ceviri)


def baska_il_var_mi(metin):
    sade = konum_anahtari(metin)

    # İl adından sonra gelebilecek yaygın çekim ekleri.
    # Apostrof hem bulunabilir hem bulunmayabilir.
    ekler = (
        r"(?:"
        r"da|de|ta|te|"
        r"dan|den|tan|ten|"
        r"a|e|ya|ye|"
        r"i|ı|u|ü|"
        r"yi|yı|yu|yü|"
        r"na|ne|"
        r"in|ın|un|ün|"
        r"nin|nın|nun|nün|"
        r"daki|deki|taki|teki|"
        r"dan|den|tan|ten"
        r")"
    )

    for il in TURKIYE_ILLERI:
        il_anahtar = konum_anahtari(il)

        if il_anahtar == "samsun":
            continue

        desen = (
            r"(?<![a-z])"
            + re.escape(il_anahtar)
            + r"(?:['’]?"
            + ekler
            + r")?"
            + r"(?![a-z])"
        )

        if re.search(desen, sade):
            print(
                f"   [FİLTRE - RED] Samsun dışı il adı bulundu: {il}"
            )
            return True

    return False


def mesaj_govdesi_temizle(metin):
    satirlar = []
    for satir in metin.splitlines():
        satir = satir.strip()
        if not satir:
            continue
        if re.fullmatch(r"\d{1,2}:\d{2}", satir):
            continue
        satirlar.append(satir)
    return " ".join(satirlar).strip()


def samsun_tevkili_mi(metin, sohbet_adi=None):
    def filtre_red_logla(neden):
        if sohbet_adi:
            sohbet_logla(
                sohbet_adi,
                "FILTRE_RED_NEDENI",
                mesaj=metin,
                neden=neden
            )

    sade = turkce_kucuk(metin)

    # Başka bir il adı geçiyorsa mesajı güvenli tarafta kalarak reddet.
    if baska_il_var_mi(metin):
        filtre_red_logla("Mesajda Samsun dışındaki bir il adı bulundu.")
        return False

    haric = [yer for yer in HARIC_LOKASYONLAR if yer in sade]
    if haric:
        print(f"   [FİLTRE - RED] Kara liste ilçe bulundu: {haric}")
        filtre_red_logla(f"Hariç tutulan ilçe bulundu: {haric}")
        return False

    yerler = []

    for yer in SAMSUN_LOKASYONLARI:
        if yer in sade:
            yerler.append(yer)

    ozel_lokasyonlar = {
        "omü": (
            r"(?<!\w)omü"
            r"(?:['’]?(?:den|dan|de|da|ye|ya|yü|yu|yı|yi))?"
            r"(?!\w)"
        ),
        "omu": (
            r"(?<!\w)omu"
            r"(?:['’]?(?:den|dan|de|da|ye|ya|yu|yı|yi))?"
            r"(?!\w)"
        ),
    }

    for yer, desen in ozel_lokasyonlar.items():
        if re.search(desen, sade):
            yerler.append(yer)

    # BAM tek başına lokasyon sayılmaz.
    # Mesajda Samsun'a ait şehir veya ilçe zaten bulunuyorsa kabul edilir.
    bam_deseni = (
        r"(?<!\w)bam"
        r"(?:['’]?(?:da|de|ta|te|dan|den|tan|ten))?"
        r"(?!\w)"
    )

    if yerler and re.search(bam_deseni, sade):
        yerler.append("bam")

    if not yerler:
        print("   [FİLTRE - RED] Samsun lokasyonu bulunamadı.")
        filtre_red_logla("Samsun lokasyonu bulunamadı.")
        return False

    islemler = [islem for islem in HUKUKI_ISLEMLER if islem in sade]
    genel_arama = any(ifade in sade for ifade in GENEL_MESLEKTAS_ARAMA)
    if not islemler and not genel_arama:
        print("   [FİLTRE - RED] Hukuki işlem veya genel meslektaş araması bulunamadı.")
        filtre_red_logla("Hukuki işlem veya genel meslektaş araması bulunamadı.")
        return False

    talepler = [talep for talep in TALEP_IFADELERI if talep in sade]
    if not talepler:
        print("   [FİLTRE - RED] Talep ifadesi bulunamadı.")
        filtre_red_logla("Talep ifadesi bulunamadı.")
        return False

    print(f"   [FİLTRE - ONAY] Lokasyon: {yerler} | Konu: {islemler} | Talep: {talepler}")
    return True


def giden_mesaj_mi(driver, element, metin, sohbet_adi):
    try:
        html = element.get_attribute("outerHTML") or ""
        class_adi = element.get_attribute("class") or ""

        if (
            'data-id="true_' in html
            or "message-out" in class_adi
            or "message-out" in html
        ):
            return True

    except WebDriverException as hata:
        sohbet_logla(
            sohbet_adi,
            "GIDEN_MESAJ_KONTROL_ILK_SELENIUM_HATASI",
            hata_turu=type(hata).__name__,
            hata_mesaji=str(hata),
            neden="Mesajın HTML veya class bilgisi okunamadı."
        )
        return False

    try:
        main_genislik = driver.find_element(
            By.XPATH, '//div[@id="main"]'
        ).size["width"]

        if element.location["x"] > main_genislik * 0.30:
            return True

    except WebDriverException as hata:
        sohbet_logla(
            sohbet_adi,
            "GIDEN_MESAJ_KONTROL_KONUM_SELENIUM_HATASI",
            hata_turu=type(hata).__name__,
            hata_mesaji=str(hata),
            neden="Sohbet genişliği veya mesaj konumu okunamadı."
        )


    return False

def mesaj_bilgilerini_cikar(element):
    ham_metin = getattr(element, "text", "") or ""
    tam_metin = ham_metin.strip()
    govde = mesaj_govdesi_temizle(tam_metin)

    tarih_bilgisi = "Bilinmiyor"
    mesaj_zamani = None
    saat_dakika = None

    # WhatsApp'ın tarih bilgisini tam datetime'a dönüştür.
    try:
        pre_text = element.find_elements(
            By.XPATH,
            './/*[@data-pre-plain-text]'
        )

        if pre_text:
            ham_tarih = (
                pre_text[0].get_attribute("data-pre-plain-text") or ""
            ).strip()

            if ham_tarih:
                tarih_bilgisi = ham_tarih

                # Örnek: [00:17, 28.10.2026] Gönderen:
                eslesme = re.search(
                    r"\[(\d{1,2}:\d{2})(?::\d{2})?,\s*(\d{1,2}\.\d{1,2}\.\d{4})\]",
                    ham_tarih
                )

                if eslesme:
                    saat_metni = eslesme.group(1)
                    tarih_metni = eslesme.group(2)

                    mesaj_zamani = datetime.strptime(
                        f"{tarih_metni} {saat_metni}",
                        "%d.%m.%Y %H:%M"
                    )

                    saat_dakika = (
                        mesaj_zamani.hour,
                        mesaj_zamani.minute
                    )
                else:
                    olay_logla(
                        "MESAJ_TARIHI_PARSLANAMADI",
                        seviye="WARNING",
                        tarih_bilgisi=ham_tarih
                    )

    except (ValueError, TypeError) as hata:
        olay_logla(
            "MESAJ_TARIHI_DONUSTURME_HATASI",
            seviye="WARNING",
            hata_turu=type(hata).__name__,
            hata_mesaji=str(hata),
            tarih_bilgisi=tarih_bilgisi
        )

    # Mesaj kimliğini al.
    data_id = element.get_attribute("data-id")

    if not data_id:
        alt = element.find_elements(
            By.XPATH,
            './/*[@data-id]'
        )
        if alt:
            data_id = alt[0].get_attribute("data-id")

    # WhatsApp'ın iç data-id'sini al veya satır sırasını/zamanı benzersiz yap
    row_index = element.get_attribute("aria-rowindex") or ""
    if data_id:
        parmak_izi = f"{data_id}"
    elif tarih_bilgisi != "Bilinmiyor":
        parmak_izi = f"{tarih_bilgisi}_{row_index}_{govde}"
    else:
        parmak_izi = f"{time.time()}_{govde}"

    return {
        "parmak_izi": parmak_izi,
        "tarih": tarih_bilgisi,
        "mesaj_zamani": mesaj_zamani,
        "saat_dakika": saat_dakika,
        "govde": govde,
        "tam_metin": tam_metin
    }


def mesaji_alintila(driver, actions, row_element, beklenen_metin, sohbet_adi=None, beklenen_sohbet_anahtari=None):
    def alinti_logla(olay, **alanlar):
        sohbet_logla(
            sohbet_adi or "Bilinmeyen_Sohbet",
            olay,
            mesaj=beklenen_metin,
            **alanlar
        )
    if (
        beklenen_sohbet_anahtari is None
        or not sohbet_ayni_mi(driver, beklenen_sohbet_anahtari)
    ):
        alinti_logla(
            "ALINTILAMA_IPTAL",
            neden="Aktif sohbet doğrulanamadı veya değişti."
        )
        return False

    alinti_logla("ALINTILAMA_BASLADI")
    print("\n   [ALINTI-DEBUG] ===== ALINTILAMA BAŞLADI =====")

    try:
        # Varsa açık kalan eski alıntıyı kapat
        driver.execute_script("""
                    var b = document.querySelector('[data-testid="quoted-message-close"]') || 
                            document.querySelector('footer span[data-icon="x"]');
                    if (b) {
                        var btn = b.closest('div[role="button"]') || b.closest('button') || b;
                        var opts = { bubbles: true, cancelable: true, view: window };
                        btn.dispatchEvent(new MouseEvent('mousedown', opts));
                        btn.dispatchEvent(new MouseEvent('mouseup', opts));
                        btn.click();
                    }
                """)
        time.sleep(0.25)

        # 1. Mesaj balonunu bul
        alinti_log_ve_terminal("1/6: Mesaj balonu aranıyor...")

        balonlar = row_element.find_elements(
            By.CSS_SELECTOR, '[data-testid="msg-container"]'
        )

        # Kalabalık detay - Sadece log dosyasına gider, terminali kirletmez
        alinti_sadece_log(f"Bulunan balon sayısı: {len(balonlar)}")

        alinti_logla(
            "ALINTI_BALONU_ARANDI",
            bulunan_balon_sayisi=len(balonlar)
        )

        balon = next(
            (e for e in balonlar if e.is_displayed()),
            None
        )
        if balon is None:
            alinti_sadece_log("msg-container bulunamadı; row_element kullanılacak.")
            balon = row_element
        else:
            alinti_sadece_log("Görünür mesaj balonu bulundu.")

        # Seçilen balon her iki durumda da loglanır.
        alinti_logla(
            "ALINTI_BALONU_SECILDI",
            gorunur=balon.is_displayed(),
            etiket=balon.tag_name,
            test_id=balon.get_attribute("data-testid"),
            balon_metni=(balon.text or "")[:300]
        )

        # Balonun temel bilgileri
        try:
            alinti_sadece_log(f"Etiket: {balon.tag_name} | Test ID: {balon.get_attribute('data-testid')} | Görünür: {balon.is_displayed()}")
            alinti_sadece_log(f"Balon metni: {(balon.text or '')[:180]!r}")

            konum = driver.execute_script("""
                const r = arguments[0].getBoundingClientRect();
                return {
                    x: Math.round(r.x),
                    y: Math.round(r.y),
                    width: Math.round(r.width),
                    height: Math.round(r.height)
                };
            """, balon)

            alinti_sadece_log(f"Balon konumu: {konum}")

        except StaleElementReferenceException as hata:
            selenium_hata_logla(
                "ALINTILAMA_BALON_BILGILERI_SELENIUM_HATASI",
                hata,
                sohbet=sohbet_adi,
                mesaj=beklenen_metin
            )

            alinti_logla(
                "ALINTILAMA_HATASI",
                asama="balon_bilgileri",
                hata_turu=type(hata).__name__,
                hata=str(hata)
            )

            alinti_sadece_log("Balon bilgileri alınırken element DOM'dan kaldırıldı.")
            return False

        # 2. Balonu görünür alana getir
        alinti_log_ve_terminal("2/6: Balon ekranda ortalanıyor...")

        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});",
            balon
        )
        time.sleep(0.3)

        alinti_sadece_log("Kaydırma tamamlandı.")

        # 3. Fareyi balonun üzerine getir
        alinti_log_ve_terminal("3/6: Fare balona götürülüyor...")

        actions.move_to_element(balon).pause(0.5).perform()
        time.sleep(0.3)

        alinti_sadece_log("Fare hareketi tamamlandı.")

        # Hover sonrasında görünen mesaj kontrollerini incele
        alinti_sadece_log("Hover sonrası mesaj kontrolleri inceleniyor...")

        kontroller = driver.execute_script("""
            const el = arguments[0];

            function visible(node) {
                const r = node.getBoundingClientRect();
                const s = getComputedStyle(node);

                return r.width > 0 &&
                       r.height > 0 &&
                       s.display !== 'none' &&
                       s.visibility !== 'hidden';
            }

            const root = el.closest('[data-testid^="conv-msg-"]')
                      || el.parentElement
                      || el;

            return Array.from(
                root.querySelectorAll(
                    'button, [role="button"], [aria-label], ' +
                    '[data-testid]'
                )
            )
            .filter(visible)
            .map(node => ({
                tag: node.tagName,
                testid: node.getAttribute('data-testid'),
                aria: node.getAttribute('aria-label'),
                title: node.getAttribute('title'),
                text: (node.innerText || node.textContent || '')
                    .trim().slice(0, 70)
            }))
            .slice(0, 25);
        """, balon)

        # Kontrol detaylarını terminale basmak yerine sadece log dosyasına atıyoruz
        if kontroller:
            alinti_sadece_log(kontroller)
        else:
            alinti_sadece_log("Hover sonrası görünür kontrol bulunamadı.")


        # 4. Seçenekler menüsünü aç (Plan A: Ok Simgesi -> Plan B: Sağ Tık)
        alinti_log_ve_terminal("4/6: Mesaj seçenekleri açılıyor...")

        if (
                beklenen_sohbet_anahtari is None
                or not sohbet_ayni_mi(driver, beklenen_sohbet_anahtari)
        ):
            alinti_logla(
                "ALINTILAMA_IPTAL",
                neden="Menü açılmadan önce sohbet değişti."
            )
            return False

        # Plan A: Ok simgesi arama (Mevcut mantığın)
        oklar = balon.find_elements(
            By.CSS_SELECTOR, '[data-testid="icon-down-context"], [data-icon="down-context"]'
        )
        ok = next((e for e in oklar if e.is_displayed()), None)

        if ok is not None:
            alinti_sadece_log("Plan A: Ok simgesi bulundu, tıklanıyor...")
            driver.execute_script("arguments[0].click();", ok)
        else:
            # Plan B: Ok bulunamadı, sağ tık yedeği devreye giriyor
            alinti_log_ve_terminal("Plan A: Ok bulunamadı, sağ tık yedeği kullanılıyor.")
            alinti_logla(
                "ALINTI_OKU_BULUNAMADI_SAG_TIK_DENENIYOR",
                neden="Ok ikonu DOM'da bulunamadığı için sağ tık yedeği kullanıldı."
            )
            try:
                actions.move_to_element(balon).context_click(balon).perform()
            except Exception as e:
                alinti_logla(
                    "ALINTILAMA_HATASI",
                    asama="sag_tik_yedegi",
                    hata=str(e)
                )

        time.sleep(0.5)
        alinti_sadece_log("Menü tetiklendi.")
        alinti_logla("MESAJ_SECENEKLERI_ACILDI")


        # 5. Görünür menüleri tara
        alinti_log_ve_terminal("5/6: Görünür menü seçenekleri aranıyor...")

        sonuc = driver.execute_script("""
            function visible(el) {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);

                return r.width > 0 &&
                       r.height > 0 &&
                       s.display !== 'none' &&
                       s.visibility !== 'hidden';
            }

            function norm(s) {
                return (s || '')
                    .trim()
                    .toLocaleLowerCase('tr-TR')
                    .replace(/\\s+/g, ' ');
            }

            const selector = [
                '[role="menu"]',
                '[role="menuitem"]',
                '[role="button"]',
                '[data-animate-dropdown-item="true"]',
                '[data-testid*="menu"]',
                'li',
                '[tabindex]'
            ].join(',');

            const items = Array.from(
                document.querySelectorAll(selector)
            ).filter(visible);

            const menuTexts = items
                .map(el => ({
                    tag: el.tagName,
                    role: el.getAttribute('role'),
                    testid: el.getAttribute('data-testid'),
                    text: norm(el.innerText || el.textContent || '')
                        .slice(0, 100)
                }))
                .filter(x => x.text)
                .slice(-30);
                
            const acikMenu = Array.from(document.querySelectorAll('[role="menu"]')).filter(visible).pop();
            
            const hedef = acikMenu ? Array.from(acikMenu.querySelectorAll('[role="menuitem"]')).find(el => {
                const t = norm(el.innerText || el.textContent || '');

                return t === 'yanıtla' ||
                       t === 'reply' ||
                       t === 'cevapla' ||
                       t === 'yanıt ver';
                })
                : null;

            return {
                menuCount: document.querySelectorAll(
                    '[role="menu"]'
                ).length,
                itemCount: items.length,
                menuTexts: menuTexts,
                hedef: hedef || null
            };
        """)

        alinti_sadece_log(sonuc)

        yanitla = sonuc["hedef"]

        if yanitla is None:
            alinti_log_ve_terminal("SONUÇ: Yanıtla menüde bulunamadı.")
            alinti_logla(
                "ALINTILAMA_HATASI",
                asama="yanitla_secimi",
                hata="Görünür menüde Yanıtla seçeneği bulunamadı."
            )
            return False
        # 6. Yanıtla seçeneğine tıkla
        alinti_log_ve_terminal("6/6: Yanıtla seçeneğine tıklanıyor...")

        driver.execute_script("""
                    const el = arguments[0];
                    const opts = { bubbles: true, cancelable: true, view: window };
                    el.dispatchEvent(new MouseEvent('mousedown', opts));
                    el.dispatchEvent(new MouseEvent('mouseup', opts));
                    el.click();
                """, yanitla)
        time.sleep(0.5)

        # Yanıt kutusunun açılıp açılmadığını kontrol et
        yanit_kutusu = driver.execute_script("""
            const selectors = [
                '[data-testid="quoted-message"]',
                '[data-testid="reply-context"]',
                '[data-testid="quoted-message-preview"]'
            ];

            const gorunurOgeler = [];

            for (const selector of selectors) {
                for (const el of document.querySelectorAll(selector)) {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);

                    if (
                        r.width > 0 &&
                        r.height > 0 &&
                        s.display !== 'none' &&
                        s.visibility !== 'hidden'
                    ) {
                        gorunurOgeler.push({
                            el: el,
                            selector: selector,
                            top: r.top,
                            text: (el.innerText || el.textContent || '')
                                .trim()
                        });
                    }
                }
            }

            // Ekranda en aşağıda bulunan görünür alıntı
            // genellikle yazma kutusundaki aktif yanıt önizlemesidir.
            gorunurOgeler.sort((a, b) => b.top - a.top);

            if (gorunurOgeler.length > 0) {
                const aktif = gorunurOgeler[0];

                return {
                    found: true,
                    selector: aktif.selector,
                    text: aktif.text.slice(0, 500)
                };
            }

            return {found: false};
        """)

        alinti_sadece_log(yanit_kutusu)
        alinti_logla(
            "YANIT_ONIZLEME_KONTROLU",
            bulundu=yanit_kutusu.get("found", False),
            secici=yanit_kutusu.get("selector"),
            onizleme_metni=yanit_kutusu.get("text", "")[:500]
        )
        if not yanit_kutusu["found"]:
            alinti_log_ve_terminal("Alıntı önizlemesi bulunamadı.")
            alinti_logla(
                "ALINTILAMA_HATASI",
                asama="onizleme_dogrulama",
                hata="Alıntı önizlemesi bulunamadı."
            )
            return False

        alinti_metni = turkce_kucuk(yanit_kutusu.get("text", ""))
        beklenen = turkce_kucuk(beklenen_metin)

        # Önizlemede mesajın gövdesinin bulunmasını doğrula.
        if beklenen not in alinti_metni:
            alinti_log_ve_terminal("HATA: Yanlış mesaj alıntılandı, iptal ediliyor.")
            alinti_logla(
                "ALINTILAMA_HATASI",
                asama="yanlis_mesaj_kontrolu",
                beklenen=beklenen,
                bulunan=alinti_metni
            )
            try:
                driver.execute_script("""
                    const el = document.querySelector(
                        '[data-testid="quoted-message-close"]'
                    );
                    if (el) {
                        const btn = el.closest(
                            '[role="button"], button'
                        ) || el;
                        btn.click();
                    }
                """)
            except WebDriverException:
                pass
            return False

        alinti_log_ve_terminal("===== ALINTILAMA TAMAMLANDI =====")
        alinti_logla(
            "ALINTILAMA_BASARILI",
            dogrulandi=True,
            alinti_metni=alinti_metni
        )
        return True

    except (
        WebDriverException,
        StaleElementReferenceException
    ) as hata:
        selenium_hata_logla(
            "ALINTILAMA_SELENIUM_HATASI",
            hata,
            sohbet=sohbet_adi,
            mesaj=beklenen_metin
        )
        alinti_logla(
            "ALINTILAMA_SELENIUM_HATASI",
            hata_turu=type(hata).__name__,
            hata_mesaji=str(hata)
        )
        print(
            f"   [ALINTI-DEBUG] SELENIUM HATASI: "
            f"{type(hata).__name__}: {hata}"
        )
        print(
            "   [ALINTI-DEBUG] ===== ALINTILAMA HATALI =====\n"
        )
        return False

    except Exception as hata:
        hata_logla(
            "ALINTILAMA_BEKLENMEYEN_HATA",
            hata,
            sohbet=sohbet_adi,
            mesaj=beklenen_metin
        )
        alinti_logla(
            "ALINTILAMA_BEKLENMEYEN_HATA",
            hata_turu=type(hata).__name__,
            hata_mesaji=str(hata)
        )
        alinti_sadece_log(f"Beklenmeyen hata: {type(hata).__name__}: {hata}")
        return False

def giden_mesaj_eslesme_sayisi(driver, metin):
    hedef = turkce_kucuk(metin)

    if not hedef:
        return 0

    try:
        sonuc = driver.execute_script("""
            const hedef = (arguments[0] || '')
                .toLocaleLowerCase('tr-TR')
                .replace(/\\s+/g, ' ')
                .trim();

            const ana = document.querySelector('#main');

            if (!ana) {
                return {
                    hata: 'MAIN_BULUNAMADI',
                    aday_sayisi: 0,
                    eslesen_sayi: 0,
                    adaylar: []
                };
            }

            function norm(s) {
                return (s || '')
                    .toLocaleLowerCase('tr-TR')
                    .replace(/\\s+/g, ' ')
                    .trim();
            }

            const seciciler = [
                '[data-testid^="conv-msg-"]',
                '[data-testid="msg-container"]',
                '[data-id^="true_"]',
                '.message-out'
            ];

            const sayilar = {};
            for (const secici of seciciler) {
                sayilar[secici] = ana.querySelectorAll(secici).length;
            }

            // Mesaj satırlarını temel al. İç içe metin elemanlarını
            // ayrı mesajlar gibi sayma.
            const adaylar = Array.from(
                ana.querySelectorAll('div[role="row"],[data-testid^="conv-msg-"]')
            );

            const detaylar = adaylar.map(el => {
                const metin = norm(el.innerText || el.textContent);
                const aria = norm(el.getAttribute('aria-label'));
                const dataId = el.getAttribute('data-id') || '';

                // WhatsApp'ın DOM yapısına göre giden mesaj işaretleri.
                const giden =
                    dataId.startsWith('true_') ||
                    /^(siz|you)(\\s|:)/i.test(aria) ||
                    /^(siz|you)(\\s|:)/i.test(metin);

                return {
                    testid: el.getAttribute('data-testid'),
                    metin: metin.slice(0, 250),
                    aria: aria.slice(0, 120),
                    dataId: dataId,
                    giden: giden,
                    metin_eslesiyor: metin.includes(hedef)
                };
            });

            // Önce hem metin hem giden mesaj koşulunu sağlayanları bul.
            const eslesenler = detaylar.filter(
                x => x.giden && x.metin_eslesiyor
            );

            return {
                hata: null,
                sayilar: sayilar,
                aday_sayisi: adaylar.length,
                eslesen_sayi: eslesenler.length,
                adaylar: detaylar
            };
        """, hedef)

        if DEBUG_MODU:
            if sonuc.get("hata"):
                olay_logla(
                    "GIDEN_MESAJ_DOM_KONTROL_HATASI",
                    seviye="WARNING",
                    hata=sonuc.get("hata"),
                    aranan_metin=metin
                )

        return int(sonuc.get("eslesen_sayi", 0))

    except (StaleElementReferenceException, WebDriverException) as e:
        selenium_hata_logla(
            "GIDEN_MESAJ_ESLESME_SELENIUM_HATASI",
            e,
            aranan_metin=metin
        )

        if DEBUG_MODU:
            print(
                f"[DOM-TEŞHİS] Selenium hatası: "
                f"{type(e).__name__}: {e}"
            )

        return 0

    except Exception as e:
        hata_logla(
            "GIDEN_MESAJ_ESLESME_BEKLENMEYEN_HATA",
            e,
            aranan_metin=metin
        )

        if DEBUG_MODU:
            print(
                f"[DOM-TEŞHİS] Beklenmeyen hata: "
                f"{type(e).__name__}: {e}"
            )

        return 0


def mesaj_gonder(driver, metin, durum=None, beklenen_sohbet_anahtari=None):
    if durum is None:
        durum = {}

    if (
        beklenen_sohbet_anahtari is None
        or not sohbet_ayni_mi(driver, beklenen_sohbet_anahtari)
    ):
        durum["asama"] = "sohbet_dogrulanamadi"
        olay_logla(
            "GONDERIM_GUVENLIK_IPTALI",
            seviye="ERROR",
            neden="Gönderim öncesinde aktif sohbet doğrulanamadı."
        )
        raise WebDriverException(
            "Güvenlik nedeniyle gönderim iptal edildi: aktif sohbet doğrulanamadı."
        )

    durum["asama"] = "yazma_alani_araniyor"

    seciciler = [
        (By.XPATH, '//footer//*[@contenteditable="true"]'),
        (By.XPATH, '//footer//*[@role="textbox"]'),
    ]

    alan = None

    for by, secici in seciciler:
        try:
            alanlar = driver.find_elements(by, secici)

            for a in alanlar:
                if a.is_displayed() and a.is_enabled():
                    alan = a
                    break

            if alan:
                break

        except WebDriverException as e:
            selenium_hata_logla(
                "MESAJ_YAZMA_ALANI_ARANIRKEN_HATA",
                e,
                secici=secici
            )
            continue

    if not alan:
        raise WebDriverException(
            "Mesaj yazma alanı tespit edilemedi."
        )

    # Gönderimden önce mevcut eşleşme sayısını kaydet.
    # Böylece aynı metinli eski bir mesajı yeni gönderim sanmayız.
    onceki_sayi = giden_mesaj_eslesme_sayisi(driver, metin)
    durum["asama"] = "yaziliyor"

    alan.click()
    time.sleep(0.1)

    alan.send_keys(Keys.CONTROL, "a")
    alan.send_keys(Keys.BACKSPACE)
    time.sleep(0.05)

    alan.send_keys(metin)
    time.sleep(0.15)

    # Bundan sonra oluşan hata gönderim belirsizliği yaratabilir.
    # Enter'dan hemen önce aktif sohbeti yeniden doğrula.
    if (
            beklenen_sohbet_anahtari is None
            or not sohbet_ayni_mi(driver, beklenen_sohbet_anahtari)
    ):
        durum["asama"] = "sohbet_degisti_enter_oncesi"
        try:
            alan.send_keys(Keys.CONTROL, "a")
            alan.send_keys(Keys.BACKSPACE)
        except WebDriverException as temizleme_hatasi:
            selenium_hata_logla(
                "SOHBET_DEGISIMI_METIN_TEMIZLEME_HATASI",
                temizleme_hatasi
            )
        olay_logla(
            "GONDERIM_GUVENLIK_IPTALI",
            seviye="ERROR",
            neden="Enter öncesinde aktif sohbet değişti.",
            beklenen_sohbet=beklenen_sohbet_anahtari
        )
        raise WebDriverException(
            "Güvenlik nedeniyle Enter gönderilmedi: aktif sohbet değişti."
        )

    durum["asama"] = "enter_cagrildi"
    alan.send_keys(Keys.ENTER)

    durum["asama"] = "komut_tamamlandi"

    yeni_sayi = onceki_sayi
    # WhatsApp'ın mesajı sohbet içinde göstermesini bekle.
    son_dogrulama_hatasi = None
    son_zaman = time.time() + 8

    while time.time() < son_zaman:
        try:
            yeni_sayi = giden_mesaj_eslesme_sayisi(
                driver, metin
            )

            son_dogrulama_hatasi = None

            if yeni_sayi > onceki_sayi:
                durum["asama"] = "dogrulandi"
                return "dogrulandi"

        except WebDriverException as e:
            son_dogrulama_hatasi = e

        time.sleep(0.4)
    if son_dogrulama_hatasi is not None:
        selenium_hata_logla(
            "GONDERIM_DOGRULAMA_BASARISIZ",
            son_dogrulama_hatasi,
            metin=metin,
            onceki_sayi=onceki_sayi,
            son_sayi=yeni_sayi
        )
    print(f"[GÖNDERİM-DEBUG] Önceki eşleşme: {onceki_sayi}")
    print(f"[GÖNDERİM-DEBUG] Sonraki eşleşme: {yeni_sayi}")
    # Komut tamamlandı ancak DOM üzerinden doğrulama yapılamadı.
    durum["asama"] = "belirsiz"
    olay_logla(
        "GONDERIM_DOGRULAMA_ZAMAN_ASIMI",
        seviye="WARNING",
        metin=metin,
        onceki_sayi=onceki_sayi,
        son_sayi=yeni_sayi,
        son_dogrulama_hatasi=(
            str(son_dogrulama_hatasi)
            if son_dogrulama_hatasi else None
        )
    )

    return "belirsiz"


def chrome_ayarla():
    options = webdriver.ChromeOptions()
    profil_yolu = os.path.join(os.path.expanduser("~"), "whatsapp_bot_session")
    options.add_argument(f"--user-data-dir={profil_yolu}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-gpu")
    options.add_argument("--start-maximized")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return webdriver.Chrome(options=options)

def aktif_sohbet_bilgisi(driver):
    """
    Aktif sohbetin görünen adını ve karşılaştırma anahtarını döndürür.
    Başlık güvenilir biçimde okunamazsa None döndürür.
    """
    sonuc = driver.execute_script("""
        const main = document.querySelector('#main');
        if (!main) return null;

        const header = main.querySelector('header');
        if (!header) return null;

        const seciciler = [
            '[data-testid="conversation-info-header-chat-title"]',
            '[data-testid="conversation-header-title"]'
        ];

        let ad = '';

        for (const selector of seciciler) {
            const el = header.querySelector(selector);
            if (el) {
                ad = (
                    el.getAttribute('title') ||
                    el.innerText ||
                    el.textContent ||
                    ''
                ).trim();

                if (ad) break;
            }
        }

        // Seçici bulunamazsa başlıktaki tekil title alanlarını dene.
        if (!ad) {
            const adaylar = Array.from(
                header.querySelectorAll('[title]')
            );

            for (const el of adaylar) {
                const title = (el.getAttribute('title') || '').trim();

                if (
                    title &&
                    !/^(çevrimiçi|online|son görülme|last seen)/i.test(title)
                ) {
                    ad = title;
                    break;
                }
            }
        }

        // Son çare: başlıktaki metnin ilk satırı.
        // Tüm başlık metnini kullanma; üye ve durum bilgileri içerebilir.
        if (!ad) {
            const metin = (header.innerText || '')
                .split('\\n')
                .map(x => x.trim())
                .filter(Boolean);

            if (metin.length) ad = metin[0];
        }

        ad = ad.replace(/\\s+/g, ' ').trim();

        if (!ad) return null;

        return { name: ad };
    """)

    if not sonuc or not sonuc.get("name"):
        return None

    ad = sohbet_adini_temizle(sonuc["name"])

    if not ad:
        return None

    return {
        "name": ad,
        "key": konum_anahtari(ad)
    }


def sohbet_adini_temizle(ad):
    """Sohbet başlığından durum metinlerini temizler."""
    ad = re.sub(r"\s+", " ", str(ad or "")).strip()

    # Fonksiyon başlık alanını öncelikli kullansa da bazı DOM
    # sürümlerinde durum bilgisi adın sonuna eklenebilir.
    ad = re.sub(
        r"\s+(?:son görülme|last seen)\b.*$",
        "",
        ad,
        flags=re.IGNORECASE
    )
    ad = re.sub(
        r"\s+(?:çevrimiçi|online)\s*$",
        "",
        ad,
        flags=re.IGNORECASE
    )

    return ad.strip(" -–|")


def sohbet_ayni_mi(driver, beklenen_anahtar):
    """Aktif sohbetin beklenen sohbetle aynı olduğunu doğrular."""
    try:
        bilgi = aktif_sohbet_bilgisi(driver)

        if bilgi is None:
            olay_logla(
                "SOHBET_KIMLIGI_OKUNAMADI",
                seviye="WARNING",
                beklenen=beklenen_anahtar
            )
            return False

        return bilgi["key"] == beklenen_anahtar

    except WebDriverException as hata:
        selenium_hata_logla(
            "SOHBET_KIMLIGI_KONTROL_HATASI",
            hata,
            beklenen=beklenen_anahtar
        )
        return False


def olay_logla(olay, seviye="INFO", **alanlar):
    """Genel bot olayını system.log dosyasına kaydeder."""
    try:
        ayrintilar = json.dumps(
            alanlar,
            ensure_ascii=False,
            default=str
        )

        mesaj = f"{olay} | {ayrintilar}"
        seviye_metni = str(seviye).upper()

        if seviye_metni == "DEBUG":
            logger.debug(mesaj)
        elif seviye_metni == "WARNING":
            logger.warning(mesaj)
        elif seviye_metni == "ERROR":
            logger.error(mesaj)
        elif seviye_metni == "CRITICAL":
            logger.critical(mesaj)
        else:
            logger.info(mesaj)

        # Yazmayı bekletmeden dosyaya aktar.
        for handler in logger.handlers:
            handler.flush()

    except Exception as hata:
        print(f"[SYSTEM-LOG-HATASI] {type(hata).__name__}: {hata}")



def hata_logla(olay, hata, **alanlar):
    """Uygulama hatasını ve traceback bilgisini system.log'a yazar."""
    try:
        import traceback

        alanlar["hata_turu"] = type(hata).__name__
        alanlar["hata_mesaji"] = str(hata)
        alanlar["traceback"] = "".join(
            traceback.format_exception(
                type(hata),
                hata,
                hata.__traceback__
            )
        )

        ayrintilar = json.dumps(
            alanlar,
            ensure_ascii=False,
            default=str
        )

        logger.error("%s | %s", olay, ayrintilar)

        for handler in logger.handlers:
            handler.flush()

    except Exception as log_hatasi:
        print(
            f"[SYSTEM-LOG-HATASI] "
            f"{type(log_hatasi).__name__}: {log_hatasi}"
        )


def selenium_hata_logla(olay, hata, **alanlar):
    """Selenium/Chrome hatasını ayrıntılı traceback ile selenium.log'a yazar."""
    try:
        import traceback

        alanlar["hata_turu"] = type(hata).__name__
        alanlar["hata_mesaji"] = str(hata)
        alanlar["traceback"] = "".join(
            traceback.format_exception(
                type(hata),
                hata,
                hata.__traceback__
            )
        )

        ayrintilar = json.dumps(
            alanlar,
            ensure_ascii=False,
            default=str
        )

        selenium_logger.error("%s | %s", olay, ayrintilar)

        for handler in selenium_logger.handlers:
            handler.flush()

    except Exception as log_hatasi:
        print(
            f"[SELENIUM-LOG-HATASI] "
            f"{type(log_hatasi).__name__}: {log_hatasi}"
        )

def sohbet_logla(sohbet_adi, olay, **alanlar):
    """Her sohbet için günlük, ayrı bir log dosyasına yazar."""
    try:
        # Dosya adında sorun çıkarabilecek karakterleri temizle.
        temiz_sohbet_adi = str(sohbet_adi or "Bilinmeyen_Sohbet")
        guvenli_ad = re.sub(
            r'[<>:"/\\|?*\x00-\x1f]',
            "_",
            temiz_sohbet_adi or "Bilinmeyen_Sohbet"
        ).strip(" .")

        if not guvenli_ad:
            guvenli_ad = "Bilinmeyen_Sohbet"

        guvenli_ad = guvenli_ad[:100]
        tarih = datetime.now().strftime("%Y-%m-%d")

        dosya_adi = f"{guvenli_ad}-{tarih}.log"
        dosya_yolu = os.path.join(
            SOHBET_LOG_DIZINI,
            dosya_adi
        )

        ayrintilar = json.dumps(
            alanlar,
            ensure_ascii=False,
            default=str
        )

        with open(dosya_yolu, "a", encoding="utf-8") as dosya:
            dosya.write(
                f"{datetime.now():%Y-%m-%d %H:%M:%S} | "
                f"{olay} | {ayrintilar}\n"
            )

    except Exception as hata:
        olay_logla(
            "SOHBET_LOG_HATASI",
            seviye="ERROR",
            sohbet=sohbet_adi,
            hata_turu=type(hata).__name__,
            hata_mesaji=str(hata)
        )

def alinti_log_ve_terminal(mesaj):
    """Hem terminale hem de debug_alinti.log dosyasına yazar (Genel adımlar için)."""
    tarih_saat = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"   [ALINTI] {mesaj}"
    print(formatted_msg)  # Terminale basar
    try:
        with open(DEBUG_ALINTI_LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(f"{tarih_saat} | {mesaj}\n")  # Loga yazar
    except Exception:
        pass

def alinti_sadece_log(mesaj):
    """Sadece debug_alinti.log dosyasına yazar, terminale ASLA basmaz (DOM adayları ve kalabalık detaylar için)."""
    tarih_saat = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(DEBUG_ALINTI_LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(f"{tarih_saat} | [DETAY] {json.dumps(mesaj, ensure_ascii=False, default=str)}\n")
    except Exception:
        pass


def alinti_debug_yaz(mesaj):
    """Log dosyasına her türlü yazar; terminale ise sadece DEBUG_MODU True ise basar."""
    tarih_saat = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Her durumda harici log dosyasına kaydet
    try:
        with open(DEBUG_ALINTI_LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(f"{tarih_saat} | {mesaj}\n")
    except Exception:
        pass

    # 2. Terminale sadece Debug modu açiksa bastır (İstersen if kontrolünü kaldırıp her türlü terminale de bastırabilirsin)
    if DEBUG_MODU:
        print(f"   [ALINTI-DEBUG] {mesaj}")


def bot_baslat():
    olay_logla(
        "BOT_BASLADI",
        debug_modu=DEBUG_MODU,
        otomatik_gonder=OTOMATIK_GONDER
    )


    driver = None
    try:
        driver = chrome_ayarla()
        driver.get("https://web.whatsapp.com")
        print("WhatsApp Web başlatılıyor...")

        WebDriverWait(driver, 120).until(
            EC.presence_of_element_located((By.XPATH, '//div[@id="main"] | //div[@id="pane-side"]'))
        )

        try:
            driver.find_element(By.XPATH, '//div[@id="main"]')
        except WebDriverException:
            print("Dinlenecek sohbet penceresini açın...")
            WebDriverWait(driver, 120).until(
                EC.presence_of_element_located((By.XPATH, '//div[@id="main"]'))
            )

        print("\nSohbet yükleniyor, geçmiş mesajlar taranıyor...")
        time.sleep(3)  # DOM'un tüm geçmiş mesajları render etmesi için bekleme

        # Aktif sohbetin güvenilir başlığını al.
        sohbet_bilgisi = aktif_sohbet_bilgisi(driver)

        if sohbet_bilgisi is None:
            olay_logla(
                "SOHBET_ADI_ALINAMADI",
                seviye="ERROR",
                aciklama="Güvenilir sohbet başlığı okunamadı; otomatik işlem durduruldu."
            )
            print("[GÜVENLİK] Aktif sohbet adı doğrulanamadı. Bot başlatılmıyor.")
            return

        sohbet_adi = sohbet_bilgisi["name"]
        sohbet_anahtari = sohbet_bilgisi["key"]

        print(f"[SOHBET] Aktif sohbet: {sohbet_adi}")

        sohbet_logla(
            sohbet_adi,
            "SOHBET_TESPIT_EDILDI",
            sohbet=sohbet_adi,
            debug_modu=DEBUG_MODU,
            otomatik_gonder=OTOMATIK_GONDER
        )

        bot_baslangic_zamani = datetime.now().replace(second=0, microsecond=0)
        simdi = bot_baslangic_zamani

        print("\n" + "=" * 55)
        print(f"BOT ÇALIŞIYOR - Başlangıç Saati: {simdi.strftime('%H:%M')}")
        print("=" * 55 + "\n")

        actions = ActionChains(driver)
        islenmis_kimlikler = deque(maxlen=HAFIZA_BOYUTU)
        son_alinti_deneme = {}
        alinti_deneme_sayilari = {}
        # Başlangıçtaki mevcut tüm mesajları hafızaya kilitle (Hızlı & Stale-Safe)
        try:
            baslangic_parmak_izleri = driver.execute_script("""
                        const ana = document.querySelector('#main');
                        if (!ana) return [];
                        const satirlar = Array.from(ana.querySelectorAll('div[role="row"]'));
                        return satirlar.map(el => {
                            // 1. data-id kontrolü
                            const dataId = el.getAttribute('data-id') || 
                                           (el.querySelector('[data-id]') ? el.querySelector('[data-id]').getAttribute('data-id') : '');
                            if (dataId) return dataId;

                            // 2. data-pre-plain-text kontrolü
                            const pre = el.querySelector('[data-pre-plain-text]');
                            const tarih = pre ? (pre.getAttribute('data-pre-plain-text') || '').trim() : '';
                            const rowIndex = el.getAttribute('aria-rowindex') || '';
                            const metin = (el.innerText || '').slice(0, 150);

                            if (tarih) {
                                return `${tarih}_${rowIndex}_${metin}`;
                            }
                            return `${Date.now()}_${rowIndex}_${metin}`;
                        });
                    """)

            for parmak_izi in baslangic_parmak_izleri:
                if parmak_izi:
                    islenmis_kimlikler.append(f"{sohbet_anahtari}::{parmak_izi}")

        except (StaleElementReferenceException, WebDriverException) as e:
            selenium_hata_logla("BASLANGIC_MESAJ_TARAMA_SELENIUM_HATASI", e)
            sohbet_logla(
                sohbet_adi,
                "BASLANGIC_MESAJ_TARAMA_SELENIUM_HATASI",
                hata_turu=type(e).__name__,
                hata_mesaji=str(e),
                neden="Başlangıç geçmişi taranırken Selenium hatası oluştu."
            )
        except Exception as e:
            hata_logla("BASLANGIC_MESAJ_TARAMA_BEKLENMEYEN_HATA", e)
            sohbet_logla(
                sohbet_adi,
                "BASLANGIC_MESAJ_TARAMA_BEKLENMEYEN_HATA",
                hata_turu=type(e).__name__,
                hata_mesaji=str(e),
                neden="Başlangıç geçmişi taranırken beklenmeyen hata oluştu."
            )

        print(f"[BAŞLANGIÇ] {len(islenmis_kimlikler)} geçmiş mesaj hafızaya kilitlendi.")
        print("Yeni mesajlar bekleniyor...\n")
        son_teshis_zamani = 0

        while True:
            if not driver.window_handles:
                print("\n[BİLGİ] Tarayıcı kapatıldı. Program sonlandırılıyor...")
                break

            # Her turun başında aktif sohbeti yeniden doğrula.
            yeni_sohbet = aktif_sohbet_bilgisi(driver)

            if yeni_sohbet is None:
                olay_logla(
                    "SOHBET_KIMLIGI_OKUNAMADI",
                    seviye="WARNING",
                    aciklama="Bu tur atlandı; mesajlar işlenmedi."
                )
                time.sleep(KONTROL_ARALIGI)
                continue

            # Kullanıcı başka sohbete geçtiyse o turda mesaj işleme.
            if yeni_sohbet["key"] != sohbet_anahtari:
                onceki_sohbet = sohbet_adi
                yeni_sohbet_adi = yeni_sohbet["name"]
                sohbet_anahtari = yeni_sohbet["key"]
                sohbet_adi = yeni_sohbet_adi
                zaman_damgasi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 1. Konsola / Terminale / Exe ekranına belirgin uyarı
                print("\n" + "=" * 55)
                print(f"[SOHBET DEĞİŞTİ] {zaman_damgasi}")
                print(f"   Ayrılınan Sohbet : {onceki_sohbet}")
                print(f"   Geçilen Sohbet   : {sohbet_adi}")
                print("=" * 55 + "\n")

                # 2. Sistem genel logu
                olay_logla(
                    "AKTIF_SOHBET_DEGISTI",
                    zaman=zaman_damgasi,
                    onceki_sohbet=onceki_sohbet,
                    yeni_sohbet=sohbet_adi
                )

                # 3. Eski sohbetin loguna ayrılma bildirimi
                sohbet_logla(
                    onceki_sohbet,
                    "SOHBETTEN_AYRILINDI",
                    zaman=zaman_damgasi,
                    gecilen_sohbet=sohbet_adi,
                    aciklama=f"{zaman_damgasi} itibarıyla '{sohbet_adi}' sohbetine geçildi."
                )

                # 4. Yeni sohbetin loguna giriş bildirimi
                sohbet_logla(
                    sohbet_adi,
                    "SOHBETE_GECILDI",
                    zaman=zaman_damgasi,
                    onceki_sohbet=onceki_sohbet,
                    debug_modu=DEBUG_MODU,
                    otomatik_gonder=OTOMATIK_GONDER,
                    aciklama=f"{zaman_damgasi} itibarıyla '{onceki_sohbet}' sohbetinden bu sohbete geçildi."
                )


                # Yeni açılan sohbetin ekranda bulunan eski mesajlarını
                # başlangıç geçmişi kabul et. Sohbet değişince geçmişe
                # dönüp otomatik yanıt verilmesini engeller.


                # Yeni açılan sohbetin ekranda bulunan eski mesajlarını JS ile hızlı & stale-safe hafızaya al
                try:
                    gecmis_parmak_izleri = driver.execute_script("""
                                        const ana = document.querySelector('#main');
                                        if (!ana) return [];
                                        const satirlar = Array.from(ana.querySelectorAll('div[role="row"]'));
                                        return satirlar.map(el => {
                                            const dataId = el.getAttribute('data-id') || 
                                                           (el.querySelector('[data-id]') ? el.querySelector('[data-id]').getAttribute('data-id') : '');
                                            if (dataId) return dataId;

                                            const pre = el.querySelector('[data-pre-plain-text]');
                                            const tarih = pre ? (pre.getAttribute('data-pre-plain-text') || '').trim() : '';
                                            const rowIndex = el.getAttribute('aria-rowindex') || '';
                                            const metin = (el.innerText || '').slice(0, 150);

                                            if (tarih) {
                                                return `${tarih}_${rowIndex}_${metin}`;
                                            }
                                            return `${Date.now()}_${rowIndex}_${metin}`;
                                        });
                                    """)

                    for parmak_izi in gecmis_parmak_izleri:
                        if parmak_izi:
                            islenmis_kimlikler.append(f"{sohbet_anahtari}::{parmak_izi}")


                except Exception as hata:
                    selenium_hata_logla(
                        "SOHBET_DEGISIMI_GECMIS_TARAMA_HATASI",
                        hata,
                        sohbet=sohbet_adi
                    )
                # Bu turda hiçbir mesajı işlemiyoruz.
                time.sleep(KONTROL_ARALIGI)
                continue

            ogeler = driver.find_elements(
                By.XPATH,
                '//div[@id="main"]//div[@role="row"]'
            )

            # Mesaj listesi alınırken sohbet değişmiş olabilir.
            kontrol_sonrasi = aktif_sohbet_bilgisi(driver)

            if (
                    kontrol_sonrasi is None
                    or kontrol_sonrasi["key"] != sohbet_anahtari
            ):
                olay_logla(
                    "SOHBET_DEGISIMI_NEDENIYLE_TUR_IPTAL",
                    seviye="WARNING",
                    beklenen=sohbet_adi
                )
                time.sleep(KONTROL_ARALIGI)
                continue

            if ogeler:
                for oge in reversed(ogeler[-5:]):
                    try:
                        bilgi = mesaj_bilgilerini_cikar(oge)

                    except (StaleElementReferenceException, WebDriverException) as e:
                        selenium_hata_logla(
                            "MESAJ_BILGISI_CIKARMA_SELENIUM_HATASI",
                            e,
                            sohbet=sohbet_adi
                        )
                        continue

                    except Exception as e:
                        hata_logla(
                            "MESAJ_BILGISI_CIKARMA_BEKLENMEYEN_HATA",
                            e,
                            sohbet=sohbet_adi
                        )
                        continue
                    govde = bilgi["govde"]
                    # Mesaj okunurken kullanıcı başka sohbete geçmiş olabilir.
                    if not sohbet_ayni_mi(driver, sohbet_anahtari):
                        olay_logla(
                            "MESAJ_ISLEME_IPTAL",
                            seviye="WARNING",
                            neden="Mesaj okunurken aktif sohbet değişti.",
                            beklenen_sohbet=sohbet_adi
                        )
                        break
                    parmak_izi = bilgi["parmak_izi"]
                    tarih = bilgi["tarih"]
                    saat_dakika = bilgi["saat_dakika"]
                    mesaj_zamani = bilgi["mesaj_zamani"]

                    if not govde:
                        sohbet_logla(
                            sohbet_adi,
                            "MESAJ_ATLANDI_BOS_GOVDE",
                            neden="Mesaj gövdesi boş olduğu için işlenmedi."
                        )
                        continue

                    # Daha önce başarıyla işlenmiş mesajı hiçbir koşulda yeniden işleme.
                    mesaj_kimligi = f"{sohbet_anahtari}::{parmak_izi}"

                    if mesaj_kimligi in islenmis_kimlikler:
                        continue


                    # Yalnızca henüz işlenmemiş, alıntı denemesi başarısız
                    # olmuş mesajları belirli aralıkla yeniden dene.
                    son_deneme = son_alinti_deneme.get(parmak_izi, 0)

                    if time.time() - son_deneme < ALINTI_TEKRAR_BEKLEME:
                        continue

                    # Bot açılmadan önceki dakikalara ait ESKİ mesajları eler
                    if mesaj_zamani is not None:
                        if mesaj_zamani < bot_baslangic_zamani:
                            sohbet_logla(
                                sohbet_adi,
                                "MESAJ_ATLANDI_BOT_BASLANGICINDAN_ONCE",
                                mesaj=govde,
                                tarih=tarih,
                                saat=saat_dakika,
                                parmak_izi=parmak_izi,
                                bot_baslangic=bot_baslangic_zamani.strftime("%Y-%m-%d %H:%M:%S"),
                                neden="Mesaj bot başlatılmadan önce gönderilmiş."
                            )
                            islenmis_kimlikler.append(mesaj_kimligi)
                            continue

                    else:
                        # Tarih okunamadıysa mesajı tarih nedeniyle eleme.
                        sohbet_logla(
                            sohbet_adi,
                            "MESAJ_ZAMANI_BILINMIYOR",
                            mesaj=govde,
                            tarih=bilgi["tarih"],
                            parmak_izi=parmak_izi,
                            neden="Mesajın gönderim tarihi okunamadığı için başlangıç zamanı kontrolü yapılamadı."
                        )

                    if YANIT_MESAJI.casefold() in govde.casefold():
                        sohbet_logla(
                            sohbet_adi,
                            "MESAJ_ATLANDI_BOT_YANIT_METNI",
                            mesaj=govde,
                            tarih=tarih,
                            saat=saat_dakika,
                            parmak_izi=parmak_izi,
                            neden="Mesaj botun yanıt metnini içeriyor."
                        )
                        islenmis_kimlikler.append(mesaj_kimligi)
                        continue

                    yon = (
                        "GİDEN (SİZ)"
                        if giden_mesaj_mi(driver, oge, bilgi["tam_metin"], sohbet_adi)
                        else "GELEN (KARŞI TARAF)"
                    )

                    print("-" * 55)
                    print(f"[ZAMAN]      {tarih}")
                    print(f"[MESAJ YÖNÜ] {yon}")
                    print(f"[METİN]      {govde!r}")

                    # Mesajın kendisini sohbet loguna kaydet.
                    sohbet_logla(
                        sohbet_adi,
                        "MESAJ_TESPIT_EDILDI",
                        tarih=tarih,
                        saat=saat_dakika,
                        yon=yon,
                        mesaj=govde,
                        parmak_izi=parmak_izi
                    )

                    # Canlı modda (DEBUG_MODU = False) kendi mesajlarımızı atla.
                    # Debug modunda (DEBUG_MODU = True) kendi yazdığımız test mesajlarını da işle.
                    if yon.startswith("GİDEN") and not KENDI_MESAJLARIMI_ISLE:
                        sohbet_logla(
                            sohbet_adi,
                            "MESAJ_ATLANDI_KULLANICIYA_AIT",
                            mesaj=govde,
                            tarih=tarih,
                            saat=saat_dakika,
                            parmak_izi=parmak_izi,
                            neden="Canlı modda kullanıcının kendi giden mesajı olduğu için işlem yapılmadı."
                        )
                        islenmis_kimlikler.append(mesaj_kimligi)
                        continue

                    # Filtre sonucu
                    uygun_mu = samsun_tevkili_mi(govde,sohbet_adi=sohbet_adi)


                    sohbet_logla(
                        sohbet_adi,
                        "FILTRE_SONUCU",
                        mesaj=govde,
                        sonuc="KABUL" if uygun_mu else "RED"
                    )

                    if not uygun_mu:
                        islenmis_kimlikler.append(mesaj_kimligi)
                        continue


                    if uygun_mu:
                        if not OTOMATIK_GONDER:
                            print("   [TEST MODU] Eşleşme sağlandı. Yanıt gönderilmedi.")

                            sohbet_logla(
                                sohbet_adi,
                                "TEST_MODU_ISLEM_YAPILMADI",
                                mesaj=govde,
                                tarih=tarih,
                                saat=saat_dakika,
                                parmak_izi=parmak_izi,
                                neden="Otomatik gönderim kapalı olduğu için işlem yapılmadı."
                            )

                            islenmis_kimlikler.append(mesaj_kimligi)
                            continue

                        print("   --> ŞARTLAR SAĞLANDI! Mesaj alıntılanıyor...")
                        time.sleep(random.uniform(0.2, 0.3))

                        alintilandi = mesaji_alintila(
                            driver,
                            actions,
                            oge,
                            govde,
                            sohbet_adi=sohbet_adi,
                            beklenen_sohbet_anahtari=sohbet_anahtari
                        )
                        if not alintilandi:
                            deneme = alinti_deneme_sayilari.get(parmak_izi, 0) + 1
                            alinti_deneme_sayilari[parmak_izi] = deneme

                            # Her başarısız denemeyi logla
                            sohbet_logla(
                                sohbet_adi,
                                "ALINTI_DENEMESI_BASARISIZ",
                                mesaj=govde,
                                deneme_no=deneme,
                                maksimum_deneme=ALINTI_MAKSIMUM_DENEME,
                                parmak_izi=parmak_izi,
                                neden="Alıntı balonu açılamadı veya doğru metin doğrulanamadı."
                            )

                            if deneme >= ALINTI_MAKSIMUM_DENEME:
                                islenmis_kimlikler.append(mesaj_kimligi)
                                son_alinti_deneme.pop(parmak_izi, None)

                                print(
                                    f"   --> [PLAN C DEVREDE] {deneme} alıntı denemesi başarısız oldu. "
                                    "İş kaçmasın diye ALINTISIZ düz yanıt gönderiliyor..."
                                )
                                sohbet_logla(
                                    sohbet_adi,
                                    "ALINTISIZ_DUZ_YANIT_GONDERILIYOR",
                                    mesaj=govde,
                                    parmak_izi=parmak_izi,
                                    neden="Alıntı başarısız oldu, talep düz mesajla yanıtlanıyor."
                                )

                                # PLAN C: Düz mesaj gönder
                                try:
                                    gonderim_durumu = {}
                                    mesaj_gonder(
                                        driver,
                                        YANIT_MESAJI,
                                        gonderim_durumu,
                                        beklenen_sohbet_anahtari=sohbet_anahtari
                                    )
                                    print(f"   --> [+] ALINTISIZ YANIT İLETİLDİ: '{YANIT_MESAJI}'\n")
                                except Exception as e:
                                    print(f"   --> [HATA] Düz yanıt da gönderilemedi: {e}\n")
                                time.sleep(1.0)
                                break

                            else:
                                son_alinti_deneme[parmak_izi] = time.time()
                                print(
                                    f"   --> [ALINTI TEKRAR] "
                                    f"{deneme}/{ALINTI_MAKSIMUM_DENEME} deneme başarısız. "
                                    f"{ALINTI_TEKRAR_BEKLEME:.0f} saniye sonra tekrar denenecek."
                                )

                            time.sleep(0.2)
                            break
                        print("   --> [BAŞARILI] Doğru mesaj alıntılandı.")
                        # Alıntı başarılı olduğundan önceki başarısızlık sayacını sıfırla.
                        alinti_deneme_sayilari.pop(parmak_izi, None)
                        gonderim_durumu = {}
                        try:
                            sonuc = mesaj_gonder(
                                driver,
                                YANIT_MESAJI,
                                gonderim_durumu,
                                beklenen_sohbet_anahtari=sohbet_anahtari
                            )

                            sohbet_logla(
                                sohbet_adi,
                                "GONDERIM_DOGRULAMA",
                                kaynak_mesaj=govde,
                                yanit=YANIT_MESAJI,
                                sonuc=sonuc,
                                asama=gonderim_durumu.get("asama", "bilinmiyor"),
                                dogrulandi=(sonuc == "dogrulandi"),
                                teslimat_dogrulandi=False,
                                okunma_dogrulandi=False
                            )

                            # Hem doğrulanmış hem belirsiz sonuçta aynı mesajı
                            # bu oturumda otomatik olarak yeniden göndermiyoruz.
                            islenmis_kimlikler.append(mesaj_kimligi)
                            son_alinti_deneme.pop(parmak_izi, None)

                            if sonuc == "dogrulandi":
                                print(
                                    "   --> [ARAYÜZDE DOĞRULANDI] "
                                    "Yeni giden mesaj satırı tespit edildi. "
                                    "Teslimat veya okunma durumu doğrulanmadı."
                                )
                            else:
                                print(
                                    "   --> [GÖNDERİM BELİRSİZ] Enter komutu tamamlandı "
                                    "ancak yeni mesaj satırı doğrulanamadı. "
                                    "Çift gönderim riskini önlemek için otomatik tekrar yok."
                                )

                        except Exception as e:
                            asama = gonderim_durumu.get("asama", "bilinmiyor")
                            if asama in ("enter_cagrildi", "komut_tamamlandi", "dogrulandi"):
                                # Enter çağrılmış olabilir; gönderim yapılmış olabilir.
                                islenmis_kimlikler.append(mesaj_kimligi)
                                son_alinti_deneme.pop(parmak_izi, None)

                                print(
                                    "   --> [GÖNDERİM BELİRSİZ] "
                                    "Enter aşamasından sonra hata oluştu. "
                                    "Otomatik tekrar yapılmayacak."
                                )
                            else:
                                # Enter aşamasına gelinmedi; yeniden deneme güvenli
                                # kabul edilir. Sonraki döngüde alıntı akışı yeniden çalışır.
                                son_alinti_deneme[parmak_izi] = time.time()

                                print(
                                    "   --> [GÖNDERİM ÖNCESİ HATA] "
                                    "Enter çağrısından önce hata oluştu."
                                )

                            if isinstance(e, WebDriverException):
                                selenium_hata_logla(
                                    "MESAJ_GONDER_SELENIUM_HATASI",
                                    e,
                                    sohbet=sohbet_adi,
                                    kaynak_mesaj=govde,
                                    yanit=YANIT_MESAJI,
                                    asama=asama
                                )
                            else:
                                hata_logla(
                                    "MESAJ_GONDER_BEKLENMEYEN_HATA",
                                    e,
                                    sohbet=sohbet_adi,
                                    kaynak_mesaj=govde,
                                    yanit=YANIT_MESAJI,
                                    asama=asama
                                )

                            sohbet_logla(
                                sohbet_adi,
                                "MESAJ_GONDER_HATASI",
                                kaynak_mesaj=govde,
                                yanit=YANIT_MESAJI,
                                hata_turu=type(e).__name__,
                                hata_mesaji=str(e),
                                asama=asama
                            )

                            print(
                                f"   --> [HATA DETAYI] "
                                f"{type(e).__name__}: {e}"
                            )

                        time.sleep(1.0)
                        break

            time.sleep(KONTROL_ARALIGI)

    except KeyboardInterrupt:
        olay_logla("BOT_KULLANICI_TARAFINDAN_DURDURULDU")
        print("\n[BİLGİ] Bot kullanıcı tarafından durduruldu.")

    except (InvalidSessionIdException, NoSuchWindowException) as hata:
        olay_logla(
            "BOT_TARAYICI_KAPANDI",
            seviye="INFO",
            hata_turu=type(hata).__name__,
            hata_mesaji=str(hata)
        )

        sohbet_logla(
            sohbet_adi if "sohbet_adi" in locals() else "Bilinmeyen_Sohbet",
            "BOT_TARAYICI_KAPANDI",
            hata_turu=type(hata).__name__,
            hata_mesaji=str(hata)
        )

        print(
            "\n[BİLGİ] Chrome penceresi veya Selenium oturumu kapandı. "
            "Bot sonlandırılıyor."
        )

    except WebDriverException as hata:
        selenium_hata_logla(
            "BOT_SELENIUM_HATASI",
            hata
        )
        olay_logla(
            "BOT_SELENIUM_NEDENIYLE_DURDU",
            seviye="ERROR",
            hata_turu=type(hata).__name__,
            hata_mesaji=str(hata)
        )
        print(
            f"\n[HATA] Selenium hatası: "
            f"{type(hata).__name__}: {hata}"
        )


    except Exception as hata:
        hata_logla("BOT_BEKLENMEYEN_HATA", hata)
        print(
            f"\n[HATA] {type(hata).__name__}: {hata}"
        )



    finally:
        olay_logla("BOT_KAPANIYOR")

        if driver:
            try:
                driver.quit()
            except (WebDriverException, InvalidSessionIdException) as e:
                selenium_hata_logla(
                    "CHROME_KAPATMA_HATASI",
                    e
                )
            except Exception as e:
                hata_logla(
                    "CHROME_KAPATMA_BEKLENMEYEN_HATA",
                    e
                )

        olay_logla("BOT_KAPANDI")


if __name__ == "__main__":
    bot_baslat()