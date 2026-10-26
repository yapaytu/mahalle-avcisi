#!/usr/bin/env python3
"""Mahalle Avcısı — Web Dashboard & Kontrol Paneli
YapayTU © 2026

Kullanım:
  python dashboard.py
  python dashboard.py --port 5000
"""

import argparse
import json
import mimetypes
import os
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mahalle_avcisi

KOK = os.path.dirname(os.path.abspath(__file__))
CIKTI = os.path.join(KOK, "ciktilar")
WEB = os.path.join(KOK, "web")
SATIS_KITI = os.path.join(KOK, "satis-kiti")

# Global durum değişkeni
TARAMA_DURUMU = {
    "calisiyor": False,
    "mesaj": "",
    "hata": None,
    "son_semt": None,
}


class ArgsObj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def tarama_gorevi(semt, yaricap):
    global TARAMA_DURUMU
    TARAMA_DURUMU["calisiyor"] = True
    TARAMA_DURUMU["mesaj"] = f"'{semt}' taranıyor..."
    TARAMA_DURUMU["hata"] = None
    try:
        args = ArgsObj(semt=semt, yaricap=yaricap)
        mahalle_avcisi.tara(args)
        
        # Son oluşturulan klasörü tespit et
        son_dosya = os.path.join(CIKTI, ".son")
        if os.path.exists(son_dosya):
            slug_ad = os.path.basename(open(son_dosya, encoding="utf-8").read().strip())
        else:
            slug_ad = mahalle_avcisi.slug(semt.split(",")[0])
            
        # Siteleri de hemen kur
        try:
            mahalle_avcisi.kur(ArgsObj(semt=slug_ad, en_iyi=50, telefonlu=False))
        except Exception:
            pass

        TARAMA_DURUMU["son_semt"] = slug_ad
        TARAMA_DURUMU["mesaj"] = "Tarama ve siteler başarıyla hazırlandı!"
    except BaseException as e:
        msg = str(e)
        if not msg or "SystemExit" in type(e).__name__:
            msg = f"'{semt}' haritada bulunamadı. Lütfen ilçe ve mahalle adını birlikte yazın (Örn: Moda, Kadıköy, İstanbul)"
        TARAMA_DURUMU["hata"] = msg
        TARAMA_DURUMU["mesaj"] = f"Hata: {msg}"
    finally:
        TARAMA_DURUMU["calisiyor"] = False


class DashboardHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def gonder_json(self, veri, kod=200):
        icerik = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(icerik)))
        self.end_headers()
        self.wfile.write(icerik)

    def oku_json(self):
        uzunluk = int(self.headers.get("Content-Length", 0))
        if uzunluk == 0:
            return {}
        govde = self.rfile.read(uzunluk).decode("utf-8")
        try:
            return json.loads(govde)
        except Exception:
            return {}

    def dosya_sun(self, tam_yol):
        if not os.path.exists(tam_yol) or os.path.isdir(tam_yol):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return

        mime, _ = mimetypes.guess_type(tam_yol)
        if not mime:
            if tam_yol.endswith(".json"):
                mime = "application/json"
            elif tam_yol.endswith(".csv"):
                mime = "text/csv"
            else:
                mime = "application/octet-stream"

        try:
            with open(tam_yol, "rb") as f:
                icerik = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8" if "text" in mime or "json" in mime else mime)
            self.send_header("Content-Length", str(len(icerik)))
            self.end_headers()
            self.wfile.write(icerik)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        yol = url.path
        sorgu = urllib.parse.parse_qs(url.query)

        # 1. Ana sayfa
        if yol in ("/", "/index.html"):
            self.dosya_sun(os.path.join(WEB, "index.html"))
            return

        # 2. Statik dosyalar (web, ciktilar, sablonlar)
        if yol.startswith("/ciktilar/"):
            rel = yol.replace("/ciktilar/", "", 1)
            self.dosya_sun(os.path.join(CIKTI, rel))
            return

        if yol.startswith("/sablonlar/"):
            rel = yol.replace("/sablonlar/", "", 1)
            self.dosya_sun(os.path.join(KOK, "sablonlar", rel))
            return

        if yol.startswith("/web/"):
            rel = yol.replace("/web/", "", 1)
            self.dosya_sun(os.path.join(WEB, rel))
            return

        # 3. API: Tarama Durumu
        if yol == "/api/durum":
            self.gonder_json(TARAMA_DURUMU)
            return

        # 4. API: Semt Listesi
        if yol == "/api/semtler":
            semtler = []
            if os.path.exists(CIKTI):
                for item in os.listdir(CIKTI):
                    p = os.path.join(CIKTI, item)
                    if os.path.isdir(p) and os.path.exists(os.path.join(p, "dukkanlar.json")):
                        try:
                            d = json.load(open(os.path.join(p, "dukkanlar.json"), encoding="utf-8"))
                            semtler.append({
                                "slug": item,
                                "ad": d.get("semt", item),
                                "tarih": d.get("tarih", ""),
                                "toplam": len(d.get("dukkanlar", [])),
                                "telli": sum(1 for x in d.get("dukkanlar", []) if x.get("telefon")),
                            })
                        except Exception:
                            semtler.append({"slug": item, "ad": item, "toplam": 0, "telli": 0})
            
            # Son tarama
            son_semt = None
            son_dosya = os.path.join(CIKTI, ".son")
            if os.path.exists(son_dosya):
                try:
                    son_semt = os.path.basename(open(son_dosya, encoding="utf-8").read().strip())
                except Exception:
                    pass
            self.gonder_json({"semtler": semtler, "son": son_semt})
            return

        # 5. API: Dükkânlar
        if yol == "/api/dukkanlar":
            semt_slug = sorgu.get("semt", [None])[0]
            if not semt_slug:
                son_dosya = os.path.join(CIKTI, ".son")
                if os.path.exists(son_dosya):
                    try:
                        semt_slug = os.path.basename(open(son_dosya, encoding="utf-8").read().strip())
                    except Exception:
                        pass
            
            if not semt_slug or not os.path.exists(os.path.join(CIKTI, semt_slug, "dukkanlar.json")):
                self.gonder_json({"hata": "Semt verisi bulunamadı"}, 404)
                return

            try:
                klasor = os.path.join(CIKTI, semt_slug)
                veri = json.load(open(os.path.join(klasor, "dukkanlar.json"), encoding="utf-8"))
                
                # CRM verilerini ekle
                crm_yol = os.path.join(klasor, "crm.json")
                crm = {}
                if os.path.exists(crm_yol):
                    try:
                        crm = json.load(open(crm_yol, encoding="utf-8"))
                    except Exception:
                        crm = {}
                
                # Her dükkâna site kurulu mu kontrol et
                siteler_klasoru = os.path.join(klasor, "siteler")
                for x in veri.get("dukkanlar", []):
                    sl = mahalle_avcisi.slug(x.get("ad", ""))
                    site_var = os.path.exists(os.path.join(siteler_klasoru, sl, "index.html"))
                    x["site_var"] = site_var
                    x["site_yolu"] = f"/ciktilar/{semt_slug}/siteler/{sl}/index.html" if site_var else None
                    x["crm"] = crm.get(x.get("osm"), {"durum": "yeni", "notlar": ""})
                
                self.gonder_json({
                    "semt_slug": semt_slug,
                    "bilgi": veri,
                    "crm": crm,
                    "sektorler": mahalle_avcisi.SEKTOR
                })
            except Exception as e:
                self.gonder_json({"hata": str(e)}, 500)
            return

        # 6. API: Satış Kiti Belgeleri
        if yol == "/api/satis-kiti":
            rehberler = {}
            if os.path.exists(SATIS_KITI):
                for f in sorted(os.listdir(SATIS_KITI)):
                    if f.endswith(".md"):
                        try:
                            icerik = open(os.path.join(SATIS_KITI, f), encoding="utf-8").read()
                            rehberler[f] = icerik
                        except Exception:
                            pass
            self.gonder_json(rehberler)
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"404 Not Found")

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        yol = url.path
        veri = self.oku_json()

        # 1. API: Tarama Başlat
        if yol == "/api/tara":
            semt = veri.get("semt", "").strip()
            yaricap = veri.get("yaricap")
            if yaricap:
                try:
                    yaricap = int(yaricap)
                except ValueError:
                    yaricap = None

            if not semt:
                self.gonder_json({"hata": "Semt adı gerekli"}, 400)
                return

            if TARAMA_DURUMU["calisiyor"]:
                self.gonder_json({"hata": "Zaten devam eden bir tarama var"}, 409)
                return

            t = threading.Thread(target=tarama_gorevi, args=(semt, yaricap), daemon=True)
            t.start()
            self.gonder_json({"mesaj": "Tarama başlatıldı", "semt": semt})
            return

        # 2. API: Siteleri Kur
        if yol == "/api/kur":
            semt_slug = veri.get("semt")
            en_iyi = int(veri.get("en_iyi", 50))
            telefonlu = bool(veri.get("telefonlu", True))

            try:
                args = ArgsObj(
                    semt=semt_slug,
                    en_iyi=en_iyi,
                    telefonlu=telefonlu
                )
                mahalle_avcisi.kur(args)
                self.gonder_json({"mesaj": f"{en_iyi} site başarıyla kuruldu!", "tamamlandi": True})
            except Exception as e:
                self.gonder_json({"hata": str(e)}, 500)
            return

        # 3. API: CRM Durum Güncelle
        if yol == "/api/crm":
            semt_slug = veri.get("semt")
            osm_id = veri.get("id")
            durum = veri.get("durum", "yeni")
            notlar = veri.get("notlar", "")

            if not semt_slug or not osm_id:
                self.gonder_json({"hata": "Eksik parametre"}, 400)
                return

            klasor = os.path.join(CIKTI, semt_slug)
            crm_yol = os.path.join(klasor, "crm.json")
            crm = {}
            if os.path.exists(crm_yol):
                try:
                    crm = json.load(open(crm_yol, encoding="utf-8"))
                except Exception:
                    crm = {}
            
            crm[osm_id] = {
                "durum": durum,
                "notlar": notlar,
                "guncelleme": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            json.dump(crm, open(crm_yol, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            self.gonder_json({"mesaj": "Güncellendi", "crm": crm[osm_id]})
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"404 Not Found")


def baslat(port=5000, ac=True):
    sunucu = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n=======================================================")
    print(f"🎯 Mahalle Avcısı Dashboard Başlatıldı!")
    print(f"👉 Tarayıcı adresi: {url}")
    print(f"Durdurmak için: Ctrl+C")
    print(f"=======================================================\n")
    if ac:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nSunucu kapatıldı.")
        sunucu.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mahalle Avcısı Web Paneli")
    parser.add_argument("--port", type=int, default=5000, help="Sunucu portu (varsayılan: 5000)")
    parser.add_argument("--no-browser", action="store_true", help="Tarayıcıyı otomatik açma")
    args = parser.parse_args()
    baslat(port=args.port, ac=not args.no_browser)
