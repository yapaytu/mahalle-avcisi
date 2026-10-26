# Mahalle Avcısı

Semtindeki **sitesi olmayan esnafı** bulur, her birine **satış şansı puanı** verir ve en iyi 50 dükkânın her birine **kendi adıyla bir site** kurar. Kapıya site sormaya değil, hazır siteyi göstermeye gidersin.

YapayTU tarafından hazırlandı · [yapaytu.com](https://yapaytu.com) · Instagram [@yapaytu](https://instagram.com/yapaytu)

## Ne yapıyor?
1. **Tara:** Semtindeki kuaför, berber, kafe, klinik, butik… OpenStreetMap'teki bütün işletmeleri çeker, sitesi olmayanları ayırır. Adı, telefonu, adresi, çalışma saatleri listede.
2. **Puanla:** Sektör, telefon, WhatsApp'a uygun cep numarası, Instagram'ı olup sitesi olmaması gibi işaretlere göre 0–100 puan verir. Zincir mağazalar listeye girmez.
3. **Kur:** En yüksek puanlı N dükkânın her birine telefona uygun, tek sayfalık site kurar: adı, hizmetleri, "Hemen ara" ve WhatsApp butonları, harita, yol tarifi, Google için işletme bilgisi (schema.org). Sektöre göre 4 tasarım var: zarif (kuaför, güzellik, butik), modern (berber, oto, emlak), sıcak (kafe, restoran, fırın), ferah (diş, klinik, veteriner).
4. **Gez:** `galeri.html` telefonunda ziyaret listesi olur. Her dükkân için "Gittim / Evet dedi / Hayır" işaretlersin.
5. **Sat:** `satis-kiti/` içinde kapıda konuşma, teklif şablonu, itiraz cevapları ve satıştan sonra siteyi yayına alma adımları var.

## Kurulum
Sadece Python 3.9 veya üstü gerekir (macOS ve çoğu Linux'ta hazır). Paket kurulumu yok, API anahtarı yok, ücret yok.

```bash
cd mahalle-avcisi
python3 mahalle_avcisi.py tara "Kadıköy, İstanbul"
python3 mahalle_avcisi.py kur --en-iyi 50
open ciktilar/kadikoy/galeri.html      # Windows: start ciktilar\kadikoy\galeri.html
```

### Web Dashboard ile (Görsel Arayüz)
Terminal komutları yerine tüm süreci görsel bir panelden yönetmek için:
```bash
python dashboard.py
```
- Harita üzerinden tek tıkla arama yapma ve yarıçap belirleme
- Dükkânları filtreleme ve canlı mobil simülatörde (iPhone çerçevesinde) siteleri inceleme
- Müşteri ziyaret durumlarını (Ziyaret Edildi, Teklif Verildi, Satıldı) takip etme
- Satış kitine doğrudan arayüzden erişme


Küçük bir mahalle için yarıçap ver:
```bash
python3 mahalle_avcisi.py tara "Moda, Kadıköy, İstanbul" --yaricap 900
```

### Claude Code ile
Klasörde Claude Code'u aç ve yaz: `mahalle-avcisi skill'ini kullan, Kadıköy'ü tara ve en iyi 50'ye site kur.`
Satıştan sonra: `mahalle-avcisi skill'ini kullan, <dükkân> sitesini bu fotoğraf ve fiyatlarla satışa hazırla.`
Skill `.claude/skills/mahalle-avcisi/` içinde, proje klasöründe Claude Code otomatik görür.

## Örnek sonuç (Kadıköy, 24 Ekim 2026)
4.837 işletme tarandı · 3.072'sinin sitesi yok · 656'sının telefonu kayıtlı · tarama ~30 sn · 50 site < 1 sn.

## Bilmen gerekenler
- **Veri OpenStreetMap'ten gelir.** Gönüllülerin girdiği veridir; bazı dükkânlar eksik ya da kapanmış olabilir. Gitmeden önce sitesini bir kez kontrol et. "Sitesi yok" = OpenStreetMap'te site bilgisi girilmemiş demek; gidince sitesi olduğu çıkabilir.
- **Puan bir öncelik sırasıdır,** satış garantisi değil.
- **"Yarım saat" ne demek?** Taramayla 50 taslak birkaç saniyede çıkar. Satıştan sonra bir siteyi gerçek fotoğraf, fiyat ve alan adıyla yayına almak Claude Code ile ortalama yarım saat sürer (alan adı yönlendirmesinin yayılması hariç).
- **Taslakları izinsiz yayına alma.** Siteler dükkân sahibi onay verene kadar senin cihazında kalsın.
- **Toplu mesaj atma.** Satış yüz yüze yapılır.
- Fiyatı sen belirlersin; şablon `satis-kiti/02-teklif.md` neyin dahil olduğunu net yazar.

## Dosyalar
```
mahalle_avcisi.py          tara / kur / liste komutları
sablonlar/site.html        dükkân sitesi tasarımı
sablonlar/sektorler.json   sektöre göre renk, slogan, hizmet listesi, puan ağırlığı
sablonlar/galeri.html      ziyaret listesi
sablonlar/foto/            sektör fotoğrafları (temsilî, CC0) ve KAYNAKLAR.json
satis-kiti/                konuşma, teklif, satıştan sonra, itirazlar
.claude/skills/            Claude Code skill'i
```

## Lisans
MIT © YapayTU. Harita ve işletme verisi © OpenStreetMap katkıcıları (ODbL). Taslaklardaki fotoğraflar temsilîdir, CC0 / kamu malı (rawpixel, Openverse üzerinden); kaynakları `sablonlar/foto/KAYNAKLAR.json` içinde. Satıştan sonra dükkânın kendi fotoğraflarıyla değiştir.
