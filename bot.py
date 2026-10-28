import os
import random
import re
import sys
import time
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
    StaleElementReferenceException,
    WebDriverException,
)

# ==================================================
# AYARLAR
# ==================================================

YANIT_MESAJI = "ben yardımcı olabilirim"
DEBUG_MODU = False
OTOMATIK_GONDER = True

KONTROL_ARALIGI = 0.5
HAFIZA_BOYUTU = 1000

# ==================================================
# KELİME FİLTRELERİ
# ==================================================

SAMSUN_LOKASYONLARI = [
    "samsun", "smsun", "samusn", "samsn",
    "ilkadım", "ilkadim",
    "atakum", "atalum", "atkum",
    "canik", "cank", "canık",
    "çarşamba", "carsamba", "carsmaba",
    "bafra", "bafta",
    "tekkeköy", "tekkekoy",
    "kavak", "ondokuzmayıs", "ondokuzmayis", "19 mayıs", "19 mayis",
    "bam", "bölge adliye", "bolge adliye",
]

HARIC_LOKASYONLAR = [
    "alaçam", "alacam",
    "ladik",
    "vezirköprü", "vezirkopru",
    "havza",
    "terme",
    "asarcık", "asarcik",
    "ayvacık", "ayvacik",
    "salıpazarı", "salipazari",
    "yakakent",
]

HUKUKI_ISLEMLER = [
    "arabulucu", "arabuluculuk", "arabulculuk", "arabulcuk",
    "duruşma", "durusma", "drusma", "durşma", "duruşm", "dava",
    "haciz", "hacze", "hacz", "hciz",
    "keşif", "kesif", "keşfe", "kesfe",
    "adliye", "adlye",
    "mahkeme", "mhkeme",
    "icra", "icr",
    "hukuk", "ceza", "hkuk",
    "sulh", "suşh", "sluh",
    "asliye", "aslye", "aslıye",
    "ağır ceza", "agir ceza", "iş mahkemesi", "is mahkemesi",
    "tüketici", "tuketici", "aile",
    "tevkil", "tvkil",
    "yetki belgesi", "yetki", "ytki", "vekalet",
    "dosya", "dsya",
    "kalem", "fotokopi", "masraf", "sorgulama", "sorgu",
    "müzekkere", "muzekkere", "savcılık", "savcilik", "ifade",
    "tapu", "tpu", "vergi dairesi", "belediye",
]

TALEP_IFADELERI = [
    "var mı", "var mi", "varmı", "varmi", "varm", "varmıdır", "var mıdır",
    "var midir", "varmidir",
    "gidebilecek", "gidicek", "gidecek", "gidebilcek", "gidck",
    "katılabilecek", "katilabilecek", "katılacak", "katilicak", "katilacak", "katilabilcek",
    "bakabilecek", "bakıcak", "bakacak", "bakabilcek",
    "yapabilecek", "yapacak", "yapıcak", "yapabilcek",
    "alabilecek", "alıcak", "alacak", "alabilcek",
    "sorgulayabilecek", "sorgulayacak", "sorgulayabilcek",
    "yardımcı olabilecek", "yardimci olabilecek", "yardımcı olabilir misiniz",
    "yardimci olabilir misiniz", "yardımcı olacak", "yardimci olacak",
    "yardımcı", "yardimci", "yardim", "yardım",
    "meslektaş", "meslektas", "mslektas",
    "kim var", "kimse var mı", "kimse var mi", "kimse varmı",
]

# ==================================================
# YARDIMCI VE FİLTRE FONKSİYONLARI
# ==================================================

def turkce_kucuk(metin):
    metin = str(metin or "")
    metin = metin.replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"\s+", " ", metin).strip()


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


def samsun_tevkili_mi(metin):
    sade = turkce_kucuk(metin)

    haric = [yer for yer in HARIC_LOKASYONLAR if yer in sade]
    if haric:
        print(f"   [FİLTRE - RED] Kara liste ilçe bulundu: {haric}")
        return False

    yerler = [yer for yer in SAMSUN_LOKASYONLARI if yer in sade]
    if not yerler:
        print("   [FİLTRE - RED] Samsun lokasyonu bulunamadı.")
        return False

    islemler = [islem for islem in HUKUKI_ISLEMLER if islem in sade]
    if not islemler:
        print("   [FİLTRE - RED] Hukuki işlem konusu bulunamadı.")
        return False

    talepler = [talep for talep in TALEP_IFADELERI if talep in sade]
    if not talepler:
        print("   [FİLTRE - RED] Talep ifadesi bulunamadı.")
        return False

    print(f"   [FİLTRE - ONAY] Lokasyon: {yerler} | Konu: {islemler} | Talep: {talepler}")
    return True


def giden_mesaj_mi(driver, element, metin):
    if YANIT_MESAJI.casefold() in metin.casefold():
        return True

    try:
        main_genislik = driver.find_element(By.XPATH, '//div[@id="main"]').size["width"]
        if element.location["x"] > (main_genislik * 0.30):
            return True
    except:
        pass

    try:
        html = element.get_attribute("outerHTML") or ""
        class_adi = element.get_attribute("class") or ""
        if 'data-id="true_' in html or "message-out" in class_adi or "message-out" in html:
            return True
    except:
        pass

    return False


def mesaj_bilgilerini_cikar(element):
    tam_metin = element.text.strip()
    govde = mesaj_govdesi_temizle(tam_metin)

    tarih_bilgisi = "Bilinmiyor"
    saat_dakika = None

    try:
        pre_text = element.find_elements(By.XPATH, './/*[@data-pre-plain-text]')
        if pre_text:
            tarih_bilgisi = pre_text[0].get_attribute("data-pre-plain-text").strip()
            # Örnek: [00:17, 28.10.2026]
            zaman_eslesme = re.search(r"\[(\d{1,2}):(\d{2})", tarih_bilgisi)
            if zaman_eslesme:
                saat_dakika = (int(zaman_eslesme.group(1)), int(zaman_eslesme.group(2)))
    except:
        pass

    data_id = None
    try:
        data_id = element.get_attribute("data-id")
        if not data_id:
            alt = element.find_elements(By.XPATH, './/*[@data-id]')
            if alt:
                data_id = alt[0].get_attribute("data-id")
    except:
        pass

    if data_id:
        parmak_izi = data_id
    elif tarih_bilgisi != "Bilinmiyor":
        parmak_izi = f"{tarih_bilgisi}_{govde}"
    else:
        parmak_izi = f"TEXT_{govde}"

    return {
        "parmak_izi": parmak_izi,
        "tarih": tarih_bilgisi,
        "saat_dakika": saat_dakika,
        "govde": govde,
        "tam_metin": tam_metin
    }


def mesaji_alintila(driver, actions, row_element, beklenen_metin):
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
        print("   [ALINTI-DEBUG] 1/6: Mesaj balonu aranıyor...")

        balonlar = row_element.find_elements(
            By.CSS_SELECTOR, '[data-testid="msg-container"]'
        )

        print(
            f"   [ALINTI-DEBUG] Bulunan balon: {len(balonlar)}"
        )

        balon = next(
            (e for e in balonlar if e.is_displayed()),
            None
        )

        if balon is None:
            print(
                "   [ALINTI-DEBUG] msg-container bulunamadı; "
                "row_element kullanılacak."
            )
            balon = row_element
        else:
            print(
                "   [ALINTI-DEBUG] Görünür mesaj balonu bulundu."
            )

        # Balonun temel bilgileri
        try:
            print(
                f"   [ALINTI-DEBUG] Etiket: {balon.tag_name} | "
                f"Test ID: {balon.get_attribute('data-testid')} | "
                f"Görünür: {balon.is_displayed()}"
            )

            print(
                f"   [ALINTI-DEBUG] Balon metni: "
                f"{(balon.text or '')[:180]!r}"
            )

            konum = driver.execute_script("""
                const r = arguments[0].getBoundingClientRect();
                return {
                    x: Math.round(r.x),
                    y: Math.round(r.y),
                    width: Math.round(r.width),
                    height: Math.round(r.height)
                };
            """, balon)

            print(f"   [ALINTI-DEBUG] Balon konumu: {konum}")

        except StaleElementReferenceException:
            print(
                "   [ALINTI-DEBUG] Balon bilgileri alınırken "
                "element DOM'dan kaldırıldı."
            )
            return False

        # 2. Balonu görünür alana getir
        print("   [ALINTI-DEBUG] 2/6: Balon ekranda ortalanıyor...")

        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});",
            balon
        )
        time.sleep(0.3)

        print("   [ALINTI-DEBUG] Kaydırma tamamlandı.")

        # 3. Fareyi balonun üzerine getir
        print("   [ALINTI-DEBUG] 3/6: Fare balona götürülüyor...")

        actions.move_to_element(balon).pause(0.5).perform()
        time.sleep(0.3)

        print("   [ALINTI-DEBUG] Fare hareketi tamamlandı.")

        # Hover sonrasında görünen mesaj kontrollerini incele
        print(
            "   [ALINTI-DEBUG] Hover sonrası mesaj kontrolleri "
            "inceleniyor..."
        )

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

        if kontroller:
            for i, kontrol in enumerate(kontroller, 1):
                print(
                    f"   [ALINTI-DEBUG] Kontrol {i}: "
                    f"{kontrol}"
                )
        else:
            print(
                "   [ALINTI-DEBUG] Hover sonrası görünür "
                "kontrol bulunamadı."
            )

        # 4. Sağ tıklama
        print("   [ALINTI-DEBUG] 4/6: Mesaj seçenekleri açılıyor...")

        oklar = balon.find_elements(
            By.CSS_SELECTOR, '[data-testid="icon-down-context"]'
        )

        ok = next((e for e in oklar if e.is_displayed()), None)

        if ok is None:
            print("   [ALINTI-DEBUG] HATA: Mesaj seçenekleri oku bulunamadı.")
            return False

        driver.execute_script("arguments[0].click();", ok)
        time.sleep(0.5)

        print("   [ALINTI-DEBUG] Mesaj seçenekleri açıldı.")

        # 5. Görünür menüleri tara
        print(
            "   [ALINTI-DEBUG] 5/6: Görünür menü seçenekleri "
            "aranıyor..."
        )

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

        print(
            f"   [ALINTI-DEBUG] Görünür menü sayısı: "
            f"{sonuc['menuCount']}"
        )
        print(
            f"   [ALINTI-DEBUG] Taranan görünür öğe sayısı: "
            f"{sonuc['itemCount']}"
        )

        if sonuc["menuTexts"]:
            for i, oge in enumerate(sonuc["menuTexts"], 1):
                print(
                    f"   [ALINTI-DEBUG] Menü öğesi {i}: "
                    f"{oge}"
                )
        else:
            print(
                "   [ALINTI-DEBUG] DOM'da görünür menü metni yok."
            )

        yanitla = sonuc["hedef"]

        if yanitla is None:
            print(
                "   [ALINTI-DEBUG] SONUÇ: Yanıtla bulunamadı."
            )
            print(
                "   [ALINTI-DEBUG] Sağ tıklama WhatsApp "
                "menüsünü açmamış olabilir."
            )
            print(
                "   [ALINTI-DEBUG] ===== ALINTILAMA BAŞARISIZ =====\n"
            )
            return False
        # 6. Yanıtla seçeneğine tıkla
        print(
            "   [ALINTI-DEBUG] 6/6: Yanıtla seçeneğine tıklanıyor..."
        )

        driver.execute_script("""
                    const el = arguments[0];
                    const opts = { bubbles: true, cancelable: true, view: window };
                    el.dispatchEvent(new MouseEvent('mousedown', opts));
                    el.dispatchEvent(new MouseEvent('mouseup', opts));
                    el.click();
                """, yanitla)
        time.sleep(0.5)

        print(
            "   [ALINTI-DEBUG] Tıklama komutu tamamlandı."
        )

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

        print(
            f"   [ALINTI-DEBUG] Yanıt önizleme kontrolü: "
            f"{yanit_kutusu}"
        )
        if not yanit_kutusu["found"]:
            print("   [ALINTI-DEBUG] Alıntı önizlemesi bulunamadı.")
            return False

        alinti_metni = turkce_kucuk(yanit_kutusu.get("text", ""))
        beklenen = turkce_kucuk(beklenen_metin)

        # Önizlemede mesajın gövdesinin bulunmasını doğrula.
        if beklenen not in alinti_metni:
            print("   [ALINTI-DEBUG] HATA: Yanlış mesaj alıntılandı!")
            print(f"   [ALINTI-DEBUG] Beklenen: {beklenen!r}")
            print(f"   [ALINTI-DEBUG] Alıntı:   {alinti_metni!r}")
            print("   [ALINTI-DEBUG] Güvenlik için alıntı iptal ediliyor.")

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
        print(
            "   [ALINTI-DEBUG] ===== ALINTILAMA TAMAMLANDI =====\n"
        )
        return True

    except (
        WebDriverException,
        StaleElementReferenceException
    ) as hata:
        print(
            f"   [ALINTI-DEBUG] SELENIUM HATASI: "
            f"{type(hata).__name__}: {hata}"
        )
        print(
            "   [ALINTI-DEBUG] ===== ALINTILAMA HATALI =====\n"
        )
        return False

    except Exception as hata:
        print(
            f"   [ALINTI-DEBUG] BEKLENMEYEN HATA: "
            f"{type(hata).__name__}: {hata}"
        )
        print(
            "   [ALINTI-DEBUG] ===== ALINTILAMA HATALI =====\n"
        )
        return False

def mesaj_gonder(driver, metin):
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
        except WebDriverException:
            continue

    if not alan:
        raise WebDriverException("Mesaj yazma alanı tespit edilemedi.")

    alan.click()
    time.sleep(0.1)

    # Yazma alanındaki olası harf kalıntılarını temizle
    alan.send_keys(Keys.CONTROL, "a")
    alan.send_keys(Keys.BACKSPACE)
    time.sleep(0.05)

    alan.send_keys(metin)
    time.sleep(0.15)
    alan.send_keys(Keys.ENTER)


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


def bot_baslat():
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

        simdi = datetime.now()
        bot_baslangic_dakikasi = simdi.hour * 60 + simdi.minute

        print("\n" + "=" * 55)
        print(f"BOT ÇALIŞIYOR - Başlangıç Saati: {simdi.strftime('%H:%M')}")
        print("=" * 55 + "\n")

        actions = ActionChains(driver)
        islenmis_kimlikler = deque(maxlen=HAFIZA_BOYUTU)

        # Başlangıçtaki mevcut tüm mesajları hafızaya kilitle
        baslangic_ogeler = driver.find_elements(By.XPATH, '//div[@id="main"]//div[@role="row"]')
        for oge in baslangic_ogeler:
            try:
                bilgi = mesaj_bilgilerini_cikar(oge)
                if bilgi["parmak_izi"]:
                    islenmis_kimlikler.append(bilgi["parmak_izi"])
            except:
                continue

        print(f"[BAŞLANGIÇ] {len(islenmis_kimlikler)} geçmiş mesaj hafızaya kilitlendi.")
        print("Yeni mesajlar bekleniyor...\n")

        while True:
            if not driver.window_handles:
                print("\n[BİLGİ] Tarayıcı kapatıldı. Program sonlandırılıyor...")
                break

            ogeler = driver.find_elements(By.XPATH, '//div[@id="main"]//div[@role="row"]')

            if ogeler:
                for oge in reversed(ogeler[-5:]):
                    try:
                        bilgi = mesaj_bilgilerini_cikar(oge)
                    except (StaleElementReferenceException, WebDriverException):
                        continue

                    govde = bilgi["govde"]
                    parmak_izi = bilgi["parmak_izi"]
                    tarih = bilgi["tarih"]
                    saat_dakika = bilgi["saat_dakika"]

                    if not govde:
                        continue

                    if parmak_izi in islenmis_kimlikler:
                        continue

                    # Botun başlangıcından önceki dakikalara ait bir mesajsa atla
                    if saat_dakika:
                        mesaj_dk = saat_dakika[0] * 60 + saat_dakika[1]
                        if mesaj_dk < bot_baslangic_dakikasi:
                            islenmis_kimlikler.append(parmak_izi)
                            continue

                    if YANIT_MESAJI.casefold() in govde.casefold():
                        islenmis_kimlikler.append(parmak_izi)
                        continue

                    yon = "GİDEN (SİZ)" if giden_mesaj_mi(driver, oge, bilgi["tam_metin"]) else "GELEN (KARŞI TARAF)"

                    print("-" * 55)
                    print(f"[ZAMAN]      {tarih}")
                    print(f"[MESAJ YÖNÜ] {yon}")
                    print(f"[METİN]      {govde!r}")

                    islenmis_kimlikler.append(parmak_izi)

                    # Test aşamasında kendi mesajlarınız için bu kontrol yorumda
                    # if yon.startswith("GİDEN"):
                    #     print("   --> Kullanıcının kendi mesajı, işlem yapılmadı.")
                    #     continue

                    uygun_mu = samsun_tevkili_mi(govde)

                    if uygun_mu:
                        if DEBUG_MODU:
                            print("   [DEBUG MODU] Eşleşme sağlandı. Yanıt gönderilmedi.")
                            continue

                        if not OTOMATIK_GONDER:
                            print("   [TEST MODU] Eşleşme sağlandı. Yanıt gönderilmedi.")
                            continue

                        print("   --> ŞARTLAR SAĞLANDI! Mesaj alıntılanıyor...")
                        time.sleep(random.uniform(0.2, 0.3))

                        alintilandi = mesaji_alintila(
                            driver,
                            actions,
                            oge,
                            govde
                        )
                        if not alintilandi:
                            print(
                                "   --> [GÜVENLİK] Doğru mesaj alıntılanamadı. "
                                "Yanıt gönderilmedi."
                            )
                            time.sleep(1.0)
                            break

                        print("   --> [BAŞARILI] Doğru mesaj alıntılandı.")
                        try:
                            mesaj_gonder(driver, YANIT_MESAJI)
                            print(f"   --> [+] YANIT GÖNDERİLDİ: '{YANIT_MESAJI}'\n")
                        except WebDriverException as e:
                            print(f"   --> [HATA] Mesaj iletilemedi: {e}\n")

                        time.sleep(1.0)
                        break

            time.sleep(KONTROL_ARALIGI)

    except (NoSuchWindowException, WebDriverException):
        print("\n[BİLGİ] WhatsApp sekmesi kapatıldı. Bot durduruldu.")
    except KeyboardInterrupt:
        print("\n[BİLGİ] Bot durduruldu.")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        sys.exit(0)


if __name__ == "__main__":
    bot_baslat()