# Aşama 2 sentetik veri paketi

`gen_stage2_synthetic.py --seed 42` ile üretildi. Formatlar case brief'teki (slayt 13–14) örneklerle birebir aynıdır; gerçek veri geldiğinde sadece `DATA_DIR` değişmelidir.

## Agent'ın görebileceği dosyalar

`zones.json` üs (Merkez Us) ve 8 bölge merkezi. Kuzey Yolu ve Doğu Yolu merkezleri brief'teki değerlerdir, diğerleri üsten ~3.2 km'de 45°'lik aralıklarla yerleştirilmiştir (Güney Kapısı Yaklaşımı 1.6 km). Bölge adları brief'teki gibi Türkçe karaktersizdir.

`image_meta.json` 40 kare (her bölgeden 5), 960×540, çekim saatleri 12:00–16:00 arası 5 dakikalık ızgarada, köşe koordinatları eksen hizalı. Karelerin yerdeki genişliği 95–160 m arasında değişir (irtifa farkı). `img_000860` brief'teki değerlerle birebir aynıdır.

`tracks.csv` 203 iz, her biri 25 nokta (2 saat, 5 dk adım). Karedeki araçların izleri çekim anında kutu merkezinde biter (sapma <1 m); diğer noktalarda ~1.5 m GPS gürültüsü vardır. Havuzda hiçbir kareye bağlı olmayan ~29 dikkat dağıtıcı iz de bulunur (aralarında karede görünmeyen tehditler de var). Hiçbir iz, başka bir karenin çekim anında o karenin içinden geçmez (tespit edilmemiş araç yaratmamak için).

`field_reports.json` 36 rapor, 09:45–16:00. Yaklaşık yarısı hatalı, yanıltıcı ya da ilgisizdir.

`detections_sim.json` 1. gün modelinin çıktısını taklit eder: kutu jitter'ı (±2 px), %6 sınıf karışıklığı (van↔truck vb.), %5 kaçırılan tespit, karelerin %10'unda düşük confidence'lı yanlış pozitif. Gerçek model hazır olana kadar pipeline'ı bununla çalıştırın.

`images/` placeholder kareler (YOLO bunlarda çalışmaz; UI geliştirmesi içindir). `--kaggle-train` ile gerçek Kaggle train kareleri ve GT kutuları kullanılabilir.

## `_labels/` — agent'a VERİLMEZ

`scenario_labels.json` her kare için beklenen risk seviyesi, her araç için senaryo, iz eşleşmesi ve gürültüsüz izden hesaplanmış referans öznitelikler (mesafe trendi, yaklaşma hızı, duraklama olayları, üsse yönelim açısı, ETA); her iz için senaryo ve hız profili; her rapor için tip, hedef iz, beklenen hüküm ve alt kontroller (konum/tip/zaman/davranış). `overview.png` sahanın ve T0122'nin görsel kontrolüdür.

## Senaryolar ve beklenen seviyeler

APPROACH_WITH_STOPS (6 kare, YÜKSEK): son 60 dk'da üsse ≥1.5 km yaklaşma, ≥15 dk'lık birden fazla duraklama. T0122 bunun brief'teki örneğidir.
DIRECT_FAST_APPROACH (3 kare, KRİTİK): ~100 dk bekleme, sonra 9–12 m/s ile doğrudan üsse; ETA birkaç dakika.
LOITER_NEAR_BASE (4 kare, YÜKSEK): 2 saat boyunca üsse 0.4–3 km'de küçük bir döngüde tur + duraklama.
FRIENDLY_PATROL (3 kare): üs çevresinde sabit yarıçaplı tur. Resmi "dost devriye, kimlik teyidi yapılmıştır" raporu varsa DÜŞÜK, yoksa ORTA.
UNTRACKED: izi olmayan araç; ağır araç ve <2.5 km ya da <1.2 km ise ORTA.
TRANSIT / MOVING_AWAY / PARKED: DÜŞÜK. TRANSIT izlerinde mesafe bir süre azalıp sonra artar; sadece "mesafe azalıyor mu" kuralı bunları yanlışlıkla tehdit sayar, yönelim açısını da kullanın.

## Rapor tipleri

DOGRU_GOZLEM (destekler), YANLIS_TIP (celisir), YANLIS_DAVRANIS (celisir: duran araç için "ilerliyor" ya da hareketli araç için "hareketsiz"), YANILTICI_OLAGAN (tehdit aracı için "hareketleri olağan": konum/tip doğru, davranış çelişiyor), DOST_TEYITLI (resmi, destekler), DOST_ALDATICI (üçüncü taraf, teyitsiz dost iddiası; risk düşürülmemeli), HAYALET_KARE_ICI (raporun koordinatı bir karenin içinde ama karede öyle bir araç yok: celisir), HAYALET_KARE_DISI (dogrulanamaz), BOLGE_NORMAL ("trafik akışı normal"; bölgede tehdit varsa celisir, yoksa ilgisiz), ESKI_IHBAR ("dün gece", ilgisiz), BOLGE_GOZLEM (koordinatsız, bölge adıyla; zones.json eşlemesi gerekir), GENEL_TATBIKAT (dogrulanamaz), MANIPULASYON (rapor metninde talimat; uygulanmamalı), ZAMAN_KAYMASI ve ORNEK_ZAMAN_UYUMSUZ (aşağıya bakın).

## Bilinmesi gereken varsayımlar

Brief'teki 12:35 raporu ("39.9253N 32.8718E çevresinde 1 ağır araç, hareketleri olağan") organizatörün demosunda "tespitle uyumlu" sayılıyor. Oysa T0122 12:35'te kayda göre ~5.9 km uzakta bekliyordu; rapordaki konum aracın 14:10'daki konumu. Bu pakette bu durum `kismen_uyumlu` olarak etiketlendi ve `organizer_demo_verdict: destekler` alanı ayrıca tutuldu. Gerçek veride raporların zamana ne kadar sıkı bağlı olduğunu kontrol edin; agent'ın hem "çekim anındaki konumla uyum" hem "rapor saatindeki iz konumuyla uyum" kontrolünü ayrı ayrı yapması en sağlam yaklaşım.

Bölge etiketi (`zone_by_sector`) üsten kerterize göre 8 sektörle atanmıştır; bölgeler nokta değil koridordur (img_000860 Doğu Yolu merkezinden ~1.7 km uzakta).

Mesafeler üs merkezli düzlem yaklaşımıyla üretildi; haversine ile hesaplanan değerler <%0.2 farklıdır. Referans öznitelikler gürültüsüz izden hesaplanır; gürültülü `tracks.csv`'den hesapladığınız değerler birkaç metre farklı çıkar, duraklama eşiğini 15–25 m tutun.

Çekim saatleri 5 dakikalık ızgaradadır (brief'teki gibi). Gerçek veride ızgara dışı saat gelirse iki kayıt arasında interpolasyon yapın.

## Yeniden üretme

```
python gen_stage2_synthetic.py --out synthetic_stage2 --seed 42
python gen_stage2_synthetic.py --out synth_s7 --seed 7          # farklı dünya, aynı dağılım
python gen_stage2_synthetic.py --out synth_kaggle --kaggle-train /path/to/train
```

Birkaç farklı seed ile üretip eval betiğinizi hepsinde çalıştırmak, eşiklerin tek bir dünyaya aşırı uymasını engeller.
