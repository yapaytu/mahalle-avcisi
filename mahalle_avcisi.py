#!/usr/bin/env python3
"""Mahalle Avcısı — yapaytu.com

Semtindeki sitesi olmayan esnafı bulur, her birine satış şansı puanı verir
ve en iyi N dükkânın her birine kendi adıyla tek sayfalık bir site kurar.

  python3 mahalle_avcisi.py tara "Kadıköy, İstanbul"
  python3 mahalle_avcisi.py tara "Caferağa, Kadıköy" --yaricap 900
  python3 mahalle_avcisi.py kur --en-iyi 50
  python3 mahalle_avcisi.py liste

Veri: OpenStreetMap (© OpenStreetMap katkıcıları, ODbL). Ücretsiz, API anahtarı gerekmez.
Sadece Python 3.9+ standart kütüphanesi kullanılır, kurulum yok.
"""
import argparse
import csv
import html
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

KOK = os.path.dirname(os.path.abspath(__file__))
CIKTI = os.path.join(KOK, "ciktilar")
UA = {"User-Agent": "mahalle-avcisi/1.0 (+https://yapaytu.com/mahalle)"}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]

# ---------------------------------------------------------------- sektörler
# agirlik: bu sektörün site alma ihtimali (0-30). Randevuyla çalışan ve müşterisi
# internetten arayan işletmeler en yukarıda; zincir marketler hiç listeye girmez.
SEKTOR = json.load(open(os.path.join(KOK, "sablonlar", "sektorler.json"), encoding="utf-8"))


def sektor_bul(t):
    shop, amenity, craft, office, health = t.get("shop", ""), t.get("amenity", ""), t.get("craft", ""), t.get("office", ""), t.get("healthcare", "")
    ad = trk_kucuk(t.get("name", ""))
    if shop == "hairdresser":
        if t.get("male") == "yes" or any(k in ad for k in ("berber", "barber", "erkek kuaför")):
            return "berber"
        return "kuafor"
    if shop in ("beauty", "cosmetics", "massage") or amenity == "beauty":
        return "guzellik"
    if amenity in ("cafe",):
        return "kafe"
    if amenity in ("restaurant", "fast_food", "ice_cream", "pub", "bar"):
        return "restoran"
    if shop in ("bakery", "pastry", "confectionery", "chocolate"):
        return "firin"
    if amenity == "dentist" or health == "dentist":
        return "dis"
    if amenity == "veterinary" or shop in ("pet", "pet_grooming"):
        return "veteriner"
    if shop in ("car_repair", "car_parts", "tyres", "car") or amenity == "car_wash" or craft in ("car_repair",):
        return "oto"
    if shop in ("clothes", "shoes", "boutique", "fashion_accessories", "jewelry", "bag", "watches"):
        return "butik"
    if office == "estate_agent" or shop == "estate_agent":
        return "emlak"
    if shop in ("florist", "garden_centre"):
        return "cicekci"
    if amenity in ("clinic", "doctors") or health in ("physiotherapist", "psychotherapist", "clinic", "doctor"):
        return "saglik"
    if shop in ("optician",):
        return "optik"
    if shop in ("tailor", "dry_cleaning", "laundry") or craft in ("tailor",) or amenity == "laundry":
        return "terzi"
    return "genel"


def trk_kucuk(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def slug(s):
    s = trk_kucuk(s)
    for a, b in (("ç", "c"), ("ğ", "g"), ("ı", "i"), ("ö", "o"), ("ş", "s"), ("ü", "u"), ("â", "a"), ("î", "i"), ("û", "u")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "dukkan"


# ---------------------------------------------------------------- ağ
def get_json(url, data=None, deneme=3):
    for i in range(deneme):
        try:
            r = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(r, timeout=180) as y:
                return json.load(y)
        except Exception as e:  # ağ hatası: biraz bekleyip tekrar dene
            if i == deneme - 1:
                raise
            time.sleep(4 * (i + 1))


def konum_bul(semt):
    varyasyonlar = [semt]
    
    # 1. "kadı köy" -> "kadıköy", "yeşil yurt" -> "yeşilyurt" gibi birleşik yazılması gereken kelimeleri düzelt
    birlesik = re.sub(r'(?i)\b(\w+)\s+(paşa|pasa|köy|koy|tepe|kale|pınar|pinar|ova|kent|hisar|evler|kuyu)\b', r'\1\2', semt)
    if birlesik != semt:
        varyasyonlar.append(birlesik)
        
    # 2. Sokak, cadde, numara gibi detayları temizleyerek ana mahalleyi/ilçeyi arat
    temiz = re.sub(r'(?i)\b\w+\s+(sokak|sokağı|sokakı|sok|soka|cadde|caddesi|cad|bulvar|bulvarı|yol|yolu|no:\s*\d+|no\s*\d+)\b', '', birlesik)
    temiz = re.sub(r'\s+', ' ', temiz).strip()
    if temiz and temiz not in varyasyonlar:
        varyasyonlar.append(temiz)
        
    # 3. Virgülle yazılmışsa sondan başa doğru (İlçe, İl) kombinasyonlarını dene
    parcalar = [p.strip() for p in re.split(r'[,/]+', semt) if p.strip()]
    if len(parcalar) > 1:
        varyasyonlar.append(", ".join(parcalar[1:]))

    for v in varyasyonlar:
        q = urllib.parse.urlencode({"q": v, "format": "jsonv2", "limit": 1, "countrycodes": "tr", "accept-language": "tr"})
        try:
            s = get_json("https://nominatim.openstreetmap.org/search?" + q)
            if s:
                return s[0]
        except Exception:
            continue

    raise SystemExit(f'"{semt}" haritada bulunamadı. Lütfen ilçe ve mahalle adını şu formatta yaz: "Moda, Kadıköy, İstanbul" veya "Alsancak, Konak, İzmir"')


def overpass(sorgu):
    son = None
    for u in OVERPASS:
        try:
            return get_json(u, urllib.parse.urlencode({"data": sorgu}).encode())
        except Exception as e:
            son = e
    raise SystemExit(f"Harita sunucusuna ulaşılamadı ({son}). Birkaç dakika sonra tekrar dene.")


FILTRE = [
    'nwr["shop"]["name"]',
    'nwr["amenity"~"^(cafe|restaurant|fast_food|ice_cream|dentist|clinic|doctors|veterinary|car_wash|beauty|laundry)$"]["name"]',
    'nwr["craft"]["name"]',
    'nwr["office"~"^(estate_agent)$"]["name"]',
    'nwr["healthcare"]["name"]',
]


def tara(args):
    print(f"• Konum aranıyor: {args.semt}")
    k = konum_bul(args.semt)
    lat, lon = float(k["lat"]), float(k["lon"])
    if k.get("osm_type") == "relation" and not args.yaricap:
        alan = f"area(id:{3600000000 + int(k['osm_id'])})->.a;"
        kapsam = "(area.a)"
        print(f"  {k['display_name']}\n• Sınırlar içindeki bütün dükkânlar taranıyor (OpenStreetMap)…")
    else:
        r = args.yaricap or 1000
        alan = ""
        kapsam = f"(around:{r},{lat},{lon})"
        print(f"  {k['display_name']}\n• {r} m çevredeki dükkânlar taranıyor (OpenStreetMap)…")
    sorgu = "[out:json][timeout:150];" + alan + "(" + "".join(f + kapsam + ";" for f in FILTRE) + ");out center tags;"
    t0 = time.time()
    d = overpass(sorgu)
    E = d.get("elements", [])
    dukkanlar, gorulen = [], set()
    for e in E:
        t = e.get("tags", {})
        if any(x in t for x in ("website", "contact:website", "url", "brand:website")):
            continue  # sitesi var
        if t.get("shop") in ("vacant", "kiosk", "supermarket", "convenience", "chemist", "mall", "department_store", "lottery", "e-cigarette", "tobacco"):
            continue
        if t.get("brand") or t.get("brand:wikidata"):
            continue  # zincir / marka şube: kararı genel merkez verir
        ad = t.get("name", "").strip()
        if len(ad) < 2:
            continue
        el = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        tel = re.sub(r"\D", "", t.get("phone") or t.get("contact:phone") or "")[-10:]
        anahtar = (trk_kucuk(ad), tel) if tel else (trk_kucuk(ad), round(el["lat"] or 0, 3), round(el["lon"] or 0, 3))
        if anahtar in gorulen:
            continue  # aynı dükkân haritada hem nokta hem bina olarak girilmiş
        gorulen.add(anahtar)
        dukkanlar.append(kayit(e, t, el))
    for x in dukkanlar:
        x["puan"], x["neden"] = puanla(x)
    dukkanlar.sort(key=lambda x: -x["puan"])
    klasor = os.path.join(CIKTI, slug(args.semt.split(",")[0]))
    os.makedirs(klasor, exist_ok=True)
    json.dump({"semt": args.semt, "konum": k["display_name"], "lat": lat, "lon": lon, "tarih": time.strftime("%Y-%m-%d %H:%M"), "dukkanlar": dukkanlar},
              open(os.path.join(klasor, "dukkanlar.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(klasor, "dukkanlar.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["puan", "ad", "sektor", "telefon", "adres", "saatler", "instagram", "neden", "harita"])
        for x in dukkanlar:
            w.writerow([x["puan"], x["ad"], SEKTOR[x["sektor"]]["ad"], x["telefon"], x["adres"], x["saatler"], x["instagram"], ", ".join(x["neden"]),
                        f"https://www.openstreetmap.org/{x['osm']}"])
    open(os.path.join(KOK, "ciktilar", ".son"), "w", encoding="utf-8").write(klasor)
    telli = sum(1 for x in dukkanlar if x["telefon"])
    print(f"\n✓ {len(E)} işletme tarandı, {len(dukkanlar)} tanesinin sitesi yok ({telli} tanesinin telefonu kayıtlı). {time.time() - t0:.0f} sn.")
    print(f"  Liste: {os.path.relpath(klasor, KOK)}/dukkanlar.csv  (Excel'de açılır)\n")
    yazdir(dukkanlar[:10])
    print(f'\nSıradaki adım:  python3 mahalle_avcisi.py kur --en-iyi 50')


def kayit(e, t, el):
    tel = t.get("phone") or t.get("contact:phone") or t.get("contact:mobile") or t.get("mobile") or ""
    tel = tel_duzen(tel.split(";")[0].strip())
    adres = " ".join(x for x in (t.get("addr:street", ""), t.get("addr:housenumber", "")) if x)
    if t.get("addr:district") or t.get("addr:city"):
        adres = ", ".join(x for x in (adres, t.get("addr:suburb", ""), t.get("addr:district", "") or t.get("addr:city", "")) if x)
    ig = t.get("contact:instagram") or t.get("instagram") or ""
    return {
        "ad": t.get("name", "").strip(),
        "sektor": sektor_bul(t),
        "telefon": tel,
        "whatsapp": whatsapp(tel),
        "adres": adres,
        "saatler": t.get("opening_hours", ""),
        "instagram": ig,
        "facebook": t.get("contact:facebook") or t.get("facebook") or "",
        "eposta": t.get("email") or t.get("contact:email") or "",
        "lat": el["lat"],
        "lon": el["lon"],
        "osm": f"{e['type']}/{e['id']}",
    }


def tel_duzen(tel):
    """+905468414539 → +90 546 841 45 39 (Türkiye numaraları için okunur biçim)."""
    r = re.sub(r"\D", "", tel)
    if r.startswith("0"):
        r = "90" + r[1:]
    if len(r) == 10:
        r = "90" + r
    if len(r) == 12 and r.startswith("90"):
        return f"+90 {r[2:5]} {r[5:8]} {r[8:10]} {r[10:12]}"
    return tel


def whatsapp(tel):
    r = re.sub(r"\D", "", tel)
    if r.startswith("0"):
        r = "90" + r[1:]
    if len(r) == 10 and r.startswith("5"):
        r = "90" + r
    return r if (len(r) == 12 and r.startswith("905")) else ""


def puanla(x):
    """0-100 satış şansı. Kaba bir öncelik sırası, kesin bir tahmin değil."""
    p, n = 10, []
    s = SEKTOR[x["sektor"]]
    p += s["agirlik"]
    n.append(s["ad"].lower())
    if x["telefon"]:
        p += 25
        n.append("telefonu var")
    if x["whatsapp"]:
        p += 7
        n.append("WhatsApp'a uygun cep")
    if x["instagram"] or x["facebook"]:
        p += 12
        n.append("sosyal medyası var, sitesi yok")
    if x["saatler"]:
        p += 8
        n.append("çalışma saatleri girilmiş")
    if x["adres"]:
        p += 5
        n.append("adresi tam")
    if x["eposta"]:
        p += 3
    return min(100, p), n


def yazdir(L):
    print(f"{'PUAN':>4}  {'SEKTÖR':<11} {'DÜKKÂN':<34} TELEFON")
    for x in L:
        print(f"{x['puan']:>4}  {SEKTOR[x['sektor']]['ad']:<11} {x['ad'][:34]:<34} {x['telefon'] or '-'}")


def son_klasor(args):
    if getattr(args, "semt", None):
        k = os.path.join(CIKTI, slug(args.semt.split(",")[0]))
    else:
        try:
            k = open(os.path.join(CIKTI, ".son"), encoding="utf-8").read().strip()
        except FileNotFoundError:
            raise SystemExit('Önce tarama yap:  python3 mahalle_avcisi.py tara "Semt, İl"')
    if not os.path.exists(os.path.join(k, "dukkanlar.json")):
        raise SystemExit(f"{k} içinde dukkanlar.json yok. Önce tara komutunu çalıştır.")
    return k


# ---------------------------------------------------------------- site kurma
SABLON = open(os.path.join(KOK, "sablonlar", "site.html"), encoding="utf-8").read()
GALERI = open(os.path.join(KOK, "sablonlar", "galeri.html"), encoding="utf-8").read()
E = html.escape

GUN = {"Mo": "Pzt", "Tu": "Sal", "We": "Çar", "Th": "Per", "Fr": "Cum", "Sa": "Cmt", "Su": "Paz", "PH": "Resmî tatil", "off": "kapalı"}


def saat_tr(s):
    if not s:
        return ""
    if s.strip() == "24/7":
        return "7 gün 24 saat açık"
    for a, b in GUN.items():
        s = re.sub(rf"\b{a}\b", b, s)
    return s.replace(";", "<br>").replace(",", ", ")


FONT = {
    "zarif": "family=Cormorant+Garamond:ital,wght@1,500&family=Jost:wght@400;500;600",
    "modern": "family=Oswald:wght@600&family=Inter:wght@400;500;600",
    "sicak": "family=Fraunces:opsz,wght@9..144,600&family=Work+Sans:wght@400;500;600",
    "ferah": "family=Manrope:wght@400;500;600;700",
}


def ek_de(ad):
    """Türkçe bulunma eki: Kadıköy'de, Moda'da, Beşiktaş'ta."""
    son_unlu = next((c for c in reversed(trk_kucuk(ad)) if c in "aıoueiöü"), "e")
    unlu = "a" if son_unlu in "aıou" else "e"
    sert = trk_kucuk(ad)[-1:] in "fstkçşhp"
    return f"{ad}'{'t' if sert else 'd'}{unlu}"


def site_yap(x, semt, fotolar):
    s = SEKTOR[x["sektor"]]
    tel = x["telefon"]
    tel_link = re.sub(r"[^\d+]", "", tel)
    semtde = ek_de(semt)
    metin = lambda t: t.replace("{semt}'de", semtde).replace("{semt}", semt).replace("{ad}", x["ad"])
    hizmet = "".join(f"<li><span>{E(h)}</span><i></i><b>Fiyat için arayın</b></li>" for h in s["hizmetler"])
    wa_url = f"https://wa.me/{x['whatsapp']}?text={urllib.parse.quote('Merhaba, siteniz üzerinden yazıyorum.')}" if x["whatsapp"] else ""
    yol = f"https://www.google.com/maps/dir/?api=1&destination={x['lat']},{x['lon']}"
    butonlar = (f'<a class="d ana" href="tel:{E(tel_link)}">Hemen ara</a>' if tel else "") + (
        f'<a class="d ikinci" href="{wa_url}">WhatsApp\'tan yaz</a>' if wa_url else f'<a class="d ikinci" href="{yol}">Yol tarifi</a>')
    yapisik = (f'<a href="tel:{E(tel_link)}">Ara</a>' if tel else "") + (f'<a href="{wa_url}">WhatsApp</a>' if wa_url else f'<a href="{yol}">Yol tarifi</a>')
    d = 0.004
    bbox = f"{x['lon'] - d},{x['lat'] - d * 0.6},{x['lon'] + d},{x['lat'] + d * 0.6}"
    ld = {"@context": "https://schema.org", "@type": s["schema"], "name": x["ad"], "telephone": tel or None, "image": "img/1.jpg",
          "address": {"@type": "PostalAddress", "streetAddress": x["adres"] or None, "addressLocality": semt, "addressCountry": "TR"},
          "geo": {"@type": "GeoCoordinates", "latitude": x["lat"], "longitude": x["lon"]}, "openingHours": x["saatler"] or None}
    ld = json.dumps({k: v for k, v in ld.items() if v}, ensure_ascii=False).replace("</", "<\\/")
    bilgi = []
    if x["adres"]:
        bilgi.append(f'<div><div class="etiket">Adres</div><p>{E(x["adres"])}</p></div>')
    if x["saatler"]:
        bilgi.append(f'<div><div class="etiket">Çalışma saatleri</div><p>{saat_tr(E(x["saatler"]))}</p></div>')
    if tel:
        bilgi.append(f'<div><div class="etiket">Telefon</div><p><a href="tel:{E(tel_link)}">{E(tel)}</a></p></div>')
    if x["instagram"]:
        ig = x["instagram"].rstrip("/").split("/")[-1].lstrip("@")
        bilgi.append(f'<div><div class="etiket">Instagram</div><p><a href="https://instagram.com/{E(ig)}">@{E(ig)}</a></p></div>')
    alanlar = {
        "AD": E(x["ad"]), "SEKTOR": E(s["ad"]), "SLOGAN": E(metin(s["slogan"])), "SEMT": E(semt), "TANITIM": E(metin(s["tanitim"])),
        "RENK": s["renk"], "STIL": s["stil"], "FONTLAR": f"https://fonts.googleapis.com/css2?{FONT[s['stil']]}&display=swap",
        "HIZMETLER": hizmet, "BUTONLAR": butonlar, "YAPISIK": yapisik, "BILGI": "".join(bilgi),
        "USTTEL": f'<a class="tel" href="tel:{E(tel_link)}">{E(tel)}</a>' if tel else "",
        "SAATKISA": f'<div class="saatkisa">{saat_tr(E(x["saatler"]))}</div>' if x["saatler"] else "",
        "HARITA": f"https://www.openstreetmap.org/export/embed.html?bbox={bbox}&layer=mapnik&marker={x['lat']},{x['lon']}",
        "YOL": yol, "LD": ld, "ACIKLAMA": E(f"{x['ad']}: {semt} {s['ad'].lower()}. {metin(s['slogan'])}"),
    }
    h = SABLON.replace("{{SEMT}}'de", E(semtde))
    for k, v in alanlar.items():
        h = h.replace("{{" + k + "}}", str(v))
    return h


def kur(args):
    klasor = son_klasor(args)
    v = json.load(open(os.path.join(klasor, "dukkanlar.json"), encoding="utf-8"))
    semt = v["semt"].split(",")[0].strip()
    L = [x for x in v["dukkanlar"] if x["telefon"] or not args.telefonlu]
    L = L[: args.en_iyi]
    if not L:
        raise SystemExit("Kurulacak dükkân yok. --telefonlu bayrağını kaldırmayı ya da daha geniş bir alan taramayı dene.")
    t0 = time.time()
    hedef = os.path.join(klasor, "siteler")
    os.makedirs(hedef, exist_ok=True)
    kullan = set()
    for i, x in enumerate(L, 1):
        sl = slug(x["ad"])
        while sl in kullan:
            sl += "-2"
        kullan.add(sl)
        x["site"] = f"siteler/{sl}/index.html"
        os.makedirs(os.path.join(hedef, sl), exist_ok=True)
        # sektör fotoğrafları siteye kopyalanır (site klasörü tek başına yayına alınabilsin); komşu dükkânlarda sıra değişir
        kaynak = os.path.join(KOK, "sablonlar", "foto", x["sektor"])
        fotolar = sorted(f for f in os.listdir(kaynak) if f.endswith(".jpg"))
        fotolar = fotolar[i % len(fotolar):] + fotolar[: i % len(fotolar)] if x["sektor"] in ("kuafor",) else fotolar
        os.makedirs(os.path.join(hedef, sl, "img"), exist_ok=True)
        for j, f in enumerate(fotolar[:3], 1):
            shutil.copyfile(os.path.join(kaynak, f), os.path.join(hedef, sl, "img", f"{j}.jpg"))
        open(os.path.join(hedef, sl, "index.html"), "w", encoding="utf-8").write(site_yap(x, semt, fotolar))
        if i % 10 == 0 or i == len(L):
            print(f"• {i}/{len(L)} site kuruldu", flush=True)
    kartlar = []
    for x in L:
        s = SEKTOR[x["sektor"]]
        kartlar.append({"ad": x["ad"], "sektor": s["ad"], "renk": s["renk"], "foto": x["site"].replace("index.html", "img/1.jpg"), "puan": x["puan"], "tel": x["telefon"], "adres": x["adres"], "site": x["site"],
                        "neden": x["neden"], "id": x["osm"]})
    g = GALERI.replace("{{SEMT}}", E(semt)).replace("{{VERI}}", json.dumps(kartlar, ensure_ascii=False).replace("</", "<\\/")).replace("{{TARIH}}", v["tarih"])
    open(os.path.join(klasor, "galeri.html"), "w", encoding="utf-8").write(g)
    print(f"\n\n✓ {len(L)} dükkân, {len(L)} site. Süre: {time.time() - t0:.1f} sn.")
    print(f"  Telefonda göstereceğin galeri: {os.path.relpath(klasor, KOK)}/galeri.html")
    print("  Galeri ziyaret listesi gibi çalışır: her dükkâna 'gittim / evet / hayır' işaretleyebilirsin.")
    print("\nSatıştan sonra o dükkânın sitesini gerçek fotoğraf, fiyat ve alan adıyla yayına almak için:")
    print("  satis-kiti/03-satistan-sonra.md  (Claude Code'a 'mahalle-avcisi skill'ini kullan' demen yeterli)")


def liste(args):
    klasor = son_klasor(args)
    v = json.load(open(os.path.join(klasor, "dukkanlar.json"), encoding="utf-8"))
    yazdir(v["dukkanlar"][: args.adet])


def main():
    ap = argparse.ArgumentParser(description="Mahalle Avcısı — sitesi olmayan esnafı bul, puanla, sitesini kur. yapaytu.com")
    alt = ap.add_subparsers(dest="komut", required=True)
    a = alt.add_parser("tara", help="semtteki sitesi olmayan dükkânları bul ve puanla")
    a.add_argument("semt", help='"Kadıköy, İstanbul" veya "Moda, Kadıköy, İstanbul"')
    a.add_argument("--yaricap", type=int, help="metre; verilirse sınır yerine bu çevre taranır (mahalleler için önerilir)")
    a.set_defaults(f=tara)
    b = alt.add_parser("kur", help="en yüksek puanlı dükkânların her birine site kur")
    b.add_argument("--en-iyi", type=int, default=50)
    b.add_argument("--semt", help="son tarama yerine başka bir semt klasörü")
    b.add_argument("--telefonlu", action="store_true", default=True, help="sadece telefonu kayıtlı olanlar (varsayılan)")
    b.add_argument("--hepsi", dest="telefonlu", action="store_false", help="telefonu olmayanları da dahil et")
    b.set_defaults(f=kur)
    c = alt.add_parser("liste", help="son taramanın ilk N dükkânını göster")
    c.add_argument("--adet", type=int, default=20)
    c.add_argument("--semt")
    c.set_defaults(f=liste)
    args = ap.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
