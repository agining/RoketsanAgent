# HİSAR arayüz kılavuzu — Sürüm 2.0

Uygulama bileşenlerinden bağımsız dokümantasyon. Kapsam: ekran düzeni, üst çubuk, harita, katmanlar, filtreler, zaman çizelgesi, kayıt tablosu, detay alanları, görseller, bildirimler, açılır paneller, sohbet ve PDF kontrolünün mevcut işlevleri. Başlatma ve teknik sorun giderme bölümü içermez. Değerlendirme veya müdahale önerileri içermez.

## Dosyalar

- `kullanim-kilavuzu.pdf`: Son belge; otomatik sayfa numaralı içindekiler ve PDF yer imleri.
- `kilavuz.md`: Düzenlenebilir metin; görsel bağlantıları içerir.
- `pdf_uret.py`: Markdown ve mevcut görsellerden PDF üretir. İçindekiler çok geçişli üretimle güncellenir.
- `ekranlari_al.cjs`: Çalışan uygulamanın ekranlarını ayrı tarayıcı profilinde yakalar.
- `gorseller/manifest.json`: Çekim zamanı, görünüm boyutu, görseller ve tarayıcı hata kontrolü.
- `gorseller/kontrol-envanteri.json`: Açılan ekranlarda görünür kontrol adları.
- `gorseller/detay-basliklari.json`: Görüntülenen kayıttaki bölüm başlıkları.

## Yeniden üretme

Proje kökünden:

```bash
.venv/bin/python docs/kullanim-kilavuzu/pdf_uret.py
```

Görselleri yenilemek için uygulama 5173 portunda çalışırken:

```bash
node docs/kullanim-kilavuzu/ekranlari_al.cjs
.venv/bin/python docs/kullanim-kilavuzu/pdf_uret.py
```

Görüntüleme betiği mevcut frontend Playwright paketini ve `/usr/bin/google-chrome` kurulumunu kullanır. Ayrı profilde tema/panel değiştirir, tablo satırı seçer, 3D görünümü açar. Sunucuya yazan API istekleri ve yeni PDF üretim isteği engellenir. Ses yalnızca geçici profilde kapatılır. Kullanıcının tarayıcı tercihleri ve uygulama kaynakları değiştirilmez. Aynı adlı dokümantasyon görselleri ve manifest yeniden yazılır.

PDF üretimi mevcut sanal ortamdaki ReportLab ve Matplotlib'i kullanır; yeni uygulama bağımlılığı eklenmez. Görseller eksikse üretim durur. Koşullu karar kartları ve sesli uyarılar için veri üretilmez; gerçek boş durumlar gösterilir.

## Kaynak doğrulaması

- `frontend/src/App.tsx`: Üst çubuk, tema, bildirim paneli ve PDF düğmesi.
- `frontend/src/components/map/OperationsMap.tsx`: Harita kamera/perspektif/rota kontrolleri.
- `frontend/src/components/map/MapSidebar.tsx`: Harita araması, filtreler, katmanlar, bölgeler.
- `frontend/src/components/map/MapOverlays.tsx`: Özet, liste, onay ve sohbet panel geçişleri.
- `frontend/src/components/Timeline.tsx`, `frontend/src/store/playback.ts`: Zaman, adımlar, hız ve rota modu.
- `frontend/src/components/tracks/BottomTrackPanel.tsx`, `TrackExplorer.tsx`: Alt tablo ve bağımsız filtreler.
- `frontend/src/components/tracks/TrackDetail.tsx`: Detay kontrolleri, bölümler, görseller ve raporlar.
- `frontend/src/components/review/ReviewCard.tsx`: Koşullu form kontrol adları ve etkileri (işlem tetiklenmedi).
- `frontend/src/components/agent/AgentChat.tsx`: Gönderme, kısayollar ve sohbet yaşam döngüsü (mesaj gönderilmedi).
- `frontend/src/components/voice/VoiceAlertCard.tsx`, `frontend/src/store/voiceAlerts.ts`: Koşullu ses kartı ve yerel tercihler.
- `frontend/src/store/tracking.ts`, `watchlist.ts`, `workspace.ts`: Seçim, kamera, yerel liste ve panel durumları.
- `frontend/src/hooks/useAnalysis.ts`: Yenileme ve önceki başarılı verinin korunması.

## Kontrol

PDF sayfaları görüntüye dönüştürülerek düzen kontrolü yapılır. Metin çıkarımıyla bölüm sırası, kaldırılan bölümlerin yokluğu ve Türkçe karakterler doğrulanır. Uygulama kaynaklarında fark oluşmadığı ayrıca kontrol edilir. Çekim tarihi manifesttedir; arayüz değiştiğinde bu kılavuz tekrar doğrulanmalıdır.
