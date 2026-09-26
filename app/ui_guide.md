# HİSAR Operasyon Merkezi — Arayüz Kullanım Kılavuzu

Bu belge, kullanıcının sesli ya da yazılı "nasıl yapılır?" sorularına yanıt olarak arayüzde **hangi öğelerin
hangi sırayla vurgulanacağını** seçmek için kullanılır. Her vurgulanabilir öğenin sabit bir kimliği (ID) vardır;
arayüzde bu öğeler `data-guide="<ID>"` özniteliğiyle işaretlidir.

Kurallar (bu belgeyi değiştiren geliştiriciler için):
- Yalnızca aşağıdaki **Öğe kataloğu** tablolarında geçen ID'ler vurgulanabilir. Satır biçimi
  `| \`id\` | Ekrandaki adı | Ne işe yarar | Açtığı alan |` korunmalıdır; sunucu (`app/ui_guide.py`) geçerli
  ID listesini ve "açtığı alan" bilgisini bu tablolardan okur.
- Yeni bir öğe eklerken hem bu tabloya bir satır hem de arayüzdeki elemana `data-guide="<id>"` ekleyin.
- "Açtığı alan" sütunu yalnızca aç/kapa düğmeleri içindir: öğeye tıklanınca görünür hale gelen başka bir katalog
  öğesi. Hedef alan zaten açıksa arayüz o adımı otomatik atlar (ör. yan panel açıkken "paneli aç" adımı gösterilmez;
  zaten açık bir paneli yanlışlıkla kapatmamak için). Aç/kapa değilse `—` yazın.

---

## 1. Ekran düzeni

Ekran tam boy bir **operasyon haritasıdır**; diğer her şey haritanın üzerinde yüzer:

- **Üst çubuk** (en üst şerit): son analiz zamanı, iz sayısı, YÜKSEK/KRİTİK sayısı, onay bekleyen sayısı ve
  sağ tarafta düğmeler: "Son söz insanda" anahtarı, LLM durumu, sesli uyarı anahtarı, bildirim zili, "İz ara",
  "Nasıl yapılır?" sesli yardım, "PDF Raporu Al", "Yenile".
- **Harita paneli** (solda, açılır/kapanır): katmanlar, iz filtreleri (arama, risk, araç, senaryo, bölge),
  eşleşen izlerin kısa listesi, izleme listesi, bölgeler, izsiz tespitler. Kapalıyken solda dar bir şerit
  (ok düğmesi) görünür.
- **Harita üstü düğmeler** (sağ üst): "Operasyon Özeti", "Öncelikli Araçlar", "Analist Onayı", "Ajan". Her biri
  bir açılır panel açar; aynı düğmeye tekrar basmak paneli kapatır.
- **Harita araçları** (haritanın sol üstü): seçili ize odaklan, harita yönünü sıfırla, tam ekran;
  yanında 2D/3D ve rota izi (Gidilen / Tüm rota / Kapalı) seçicileri.
- **Zaman çizelgesi** (en altta): oynat/duraklat, başa al, 5 dk geri/ileri, hız, rota izi, zaman kaydırıcısı ve
  olay işaretleri. Harita, seçilen andaki araç konumlarını gösterir.
- **Tüm İz Kayıtları** (alt ortada açılır şerit): tüm izlerin aranabilir, filtrelenebilir, sıralanabilir tablosu.
- **İz detay paneli** (sağda): bir iz seçildiğinde açılır. İzleme listesine alma, takip, odaklanma, risk kararı,
  ajan değerlendirmesi, saha raporları, mesafe geçmişi gibi bölümler içerir.

Haritadaki araç simgeleri vurgulanamaz (harita çizimi içindedir). Kullanıcının bir araç seçmesi gerekiyorsa
harita panelindeki kısa listeyi (`sidebar-track-list`) veya tablo satırlarını (`explorer-table`) vurgulayın.

## 2. Öğe kataloğu

### 2.1 Üst çubuk (her zaman görünür)

| ID | Ekrandaki adı | Ne işe yarar | Açtığı alan |
|---|---|---|---|
| `topbar-high-critical` | YÜKSEK / KRİTİK sayacı | Yüksek ve kritik riskli uyarıların sayısı (yalnızca bilgi). | — |
| `topbar-pending` | ONAY BEKLEYEN sayacı | Analist onayı bekleyen karar sayısı (yalnızca bilgi). | — |
| `topbar-human-review` | "Son söz insanda" anahtarı | Açıkken motor ile LLM'in ayrıştığı kararlar analist onayına düşer. | — |
| `topbar-voice-alerts` | "Ses açık / Ses kapalı" anahtarı | Sesli tehdit bildirimlerini açar/kapatır. | — |
| `topbar-notifications` | Zil simgesi | İzleme listesindeki araçların bildirimlerini gösterir. | `notifications-panel` |
| `notifications-panel` | Bildirimler paneli | Bildirim listesi; bir bildirime tıklamak o araca gider. "Tümünü okundu işaretle" düğmesi burada. | — |
| `topbar-voice-guide` | "Nasıl yapılır?" mikrofon düğmesi | Sesli soru sorarak bu kılavuzla adım adım yardım alma. | — |
| `topbar-search` | "İz ara" düğmesi | Harita panelini açar ve iz arama kutusuna odaklanır. | `sidebar` |
| `topbar-pdf-report` | "PDF Raporu Al" düğmesi | YÜKSEK ve üzeri araçlar için PDF tehdit raporunu yeni sekmede üretir. | — |
| `topbar-refresh` | "Yenile" düğmesi | Analiz verisini API'den yeniden yükler. | — |

### 2.2 Harita paneli (sol)

Panel kapalıyken yalnızca `sidebar-open` görünür; diğer öğeler için önce panel açılmalıdır.

| ID | Ekrandaki adı | Ne işe yarar | Açtığı alan |
|---|---|---|---|
| `sidebar-open` | Soldaki dar şerit (katman simgesi + ok) | Harita panelini açar. | `sidebar` |
| `sidebar` | Harita Paneli | Panelin tamamı. | — |
| `sidebar-collapse` | Panel başlığındaki sol ok | Harita panelini kapatır. | — |
| `sidebar-layers` | Katmanlar | İz kayıtları, izsiz tespitler, bölgeler ve üs katmanlarını haritada göster/gizle. | — |
| `sidebar-search` | İz filtreleri → arama kutusu | İz, araç, kare veya bölge adına göre filtreler. | — |
| `filter-risk` | Risk seçimi | İzleri risk seviyesine göre filtreler (Düşük, Orta, Yüksek, Kritik, Bilinmiyor). | — |
| `filter-vehicle` | Araç seçimi | İzleri araç sınıfına göre filtreler (otomobil, kamyon, otobüs…). | — |
| `filter-scenario` | Senaryo seçimi | İzleri davranış senaryosuna göre filtreler (yaklaşma, tur atma, devriye…). | — |
| `filter-zone` | Bölge seçimi | İzleri bölgeye göre filtreler. | — |
| `filter-clear` | "Temizle" | Tüm harita filtrelerini sıfırlar; altında kaç izin görünür olduğu yazar. | — |
| `sidebar-track-list` | Filtre sonucu kısa liste | Filtreye uyan ilk 8 iz; birine tıklamak o izi seçer ve detay panelini açar. | — |
| `sidebar-watchlist` | İzleme Listesi | İzlemeye alınan araçlar; çöp kutusu simgesi listeden çıkarır. | — |
| `sidebar-zones` | Bölgeler | Bir bölgeye tıklamak haritayı o bölgeye götürür. | — |
| `sidebar-untracked` | İzsiz tespitler | İzi olmayan tespitler; birine tıklamak haritayı o konuma ve zamana götürür. | — |

Haritada görünen izler hem bu paneldeki filtrelere hem de katmanlara bağlıdır.

### 2.3 Harita üstü düğmeler ve panelleri (sağ üst)

Düğmeler aç/kapa çalışır. Aynı anda yalnızca bir panel açık olur.

| ID | Ekrandaki adı | Ne işe yarar | Açtığı alan |
|---|---|---|---|
| `overlay-summary` | "Operasyon Özeti" | Özet panelini açar/kapatır. | `summary-panel` |
| `summary-panel` | Operasyon Özeti paneli | Kare risk dağılımı (nihai ve motor), kare/araç/iz sayıları, saha raporu hükümleri, karar durumları. | — |
| `summary-assess-all` | "Riskli kareleri ajanla değerlendir" | ORTA ve üzeri kareleri LLM ajanıyla toplu değerlendirir. | — |
| `overlay-priority` | "Öncelikli Araçlar" | ORTA ve üzeri riskli araç listesini açar/kapatır. | `priority-panel` |
| `priority-panel` | Öncelikli Araçlar paneli | Riskli araçlar; birine tıklamak aracı seçer ve zamanı o ana alır. | — |
| `overlay-reviews` | "Analist Onayı" | Analist onayı panelini açar/kapatır. | `reviews-panel` |
| `reviews-panel` | Analist onayı paneli | Onay bekleyen ve karar verilmiş araçlar. | — |
| `review-analyst` | "Analist" ad kutusu | Kararlara yazılacak analist adı. | — |
| `review-levels` | Seviye düğmeleri (ilk kart) | Araç için nihai risk seviyesini seçer. Yalnızca "Son söz insanda" açıkken görünür. | — |
| `review-note` | "Not" kutusu (ilk kart) | Karara isteğe bağlı not. | — |
| `review-submit` | "Kararı kaydet" (ilk kart) | Analist kararını kaydeder. | — |
| `overlay-chat` | "Ajan" | Ajan sohbet panelini açar/kapatır. | `agent-chat` |
| `agent-chat` | Ajan sohbeti paneli | LLM ajanıyla araçlar, kareler ve raporlar hakkında sohbet. | — |
| `chat-input` | Mesaj kutusu | Ajana soru yazma. Enter gönderir. | — |
| `chat-mic` | Mikrofon düğmesi (sohbet) | Sesle yazma: bir kez bas konuş, tekrar bas bitir; metin mesaj kutusuna eklenir. | — |
| `chat-send` | Gönder düğmesi | Mesajı ajana gönderir. | — |

### 2.4 Harita araçları

| ID | Ekrandaki adı | Ne işe yarar | Açtığı alan |
|---|---|---|---|
| `map-focus-selected` | Hedef simgesi | Seçili ize haritada odaklanır (bir iz seçili olmalı). | — |
| `map-reset-view` | Döner ok | Harita yönünü sıfırlar ve tüm alanı gösterir. | — |
| `map-fullscreen` | Tam ekran | Haritayı tam ekran yapar / çıkar. | — |
| `map-view-mode` | 2D / 3D | Harita perspektifini değiştirir. | — |
| `map-trail-mode` | Gidilen / Tüm rota / Kapalı | Araç rotalarının haritada nasıl çizileceği. | — |

### 2.5 Zaman çizelgesi (alt)

| ID | Ekrandaki adı | Ne işe yarar | Açtığı alan |
|---|---|---|---|
| `timeline-restart` | Başa al | Oynatımı en başa alır. | — |
| `timeline-step-back` | Geri | 5 dakika geri gider. | — |
| `timeline-play` | Oynat / Duraklat | Zamanı oynatır ya da duraklatır. | — |
| `timeline-step-forward` | İleri | 5 dakika ileri gider. | — |
| `timeline-speed` | "Hız" seçimi | Oynatma hızı (0.5x, 1x, 2x, 4x). | — |
| `timeline-trail` | "İz" seçimi | Rota izi modu (zaman çizelgesinden). | — |
| `timeline-slider` | Zaman kaydırıcısı | Sürükleyerek istenen ana gider. | — |
| `timeline-events` | Olay işaretleri | Kaydırıcı üstündeki noktalar; tıklamak o olayın anına gider. | — |

### 2.6 Tüm İz Kayıtları (alt ortadaki şerit)

| ID | Ekrandaki adı | Ne işe yarar | Açtığı alan |
|---|---|---|---|
| `bottom-panel-toggle` | "Tüm İz Kayıtları" şeridi | İz tablosunu açar/kapatır. | `track-explorer` |
| `track-explorer` | İz tablosu paneli | Tüm izler; arama, filtre ve sıralama. | — |
| `explorer-search` | Tablo arama kutusu | İz, araç, kare veya bölgeye göre arar. | — |
| `explorer-filters` | Tablo filtreleri (Risk ve yanındakiler) | Tablodaki risk, senaryo, karar, araç, bölge ve kaynak filtreleri. | — |
| `explorer-contradictions` | "Çelişen / manipülatif rapor var" | Yalnızca çelişkili saha raporu olan izleri gösterir. | — |
| `explorer-sort` | Sıralama | Risk, üsse mesafe, gözlem zamanı veya tahmini varışa göre; ok düğmesi artan/azalan. | — |
| `explorer-clear` | "Temizle" | Tablo filtrelerini sıfırlar. | — |
| `explorer-table` | Tablo satırları | Bir satıra tıklamak izi seçer ve detay panelini açar. | — |

### 2.7 İz detay paneli (sağ)

Yalnızca bir iz seçiliyken görünür. İz seçtirmek için önce `sidebar-track-list`, `explorer-table` ya da
`priority-panel` vurgulanmalıdır.

| ID | Ekrandaki adı | Ne işe yarar | Açtığı alan |
|---|---|---|---|
| `detail-panel` | İz detayı paneli | Seçili izin tüm bilgileri. | — |
| `detail-font` | Büyüteç simgesi | Paneldeki yazı boyutunu değiştirir. | — |
| `detail-collapse` | Paneli daralt | Detay panelini gizler (seçim korunur). | — |
| `detail-close` | Çarpı (X) | İz seçimini temizler ve paneli kapatır. | — |
| `detail-watch` | "İzlemeye al / İzleniyor" | İzi izleme listesine ekler/çıkarır; izlenen araçlar için bildirim üretilir. | — |
| `detail-follow` | "Takip et" | Harita kamerası aracı takip eder. | — |
| `detail-focus` | "Haritada odaklan" | Haritayı araca yaklaştırır. | — |
| `detail-observed` | "Gözlem anına git" | Zamanı aracın görüntüde yakalandığı ana alır. | — |
| `detail-risk` | Risk Kararı bölümü | Nihai seviye, motor seviyesi ve kararın nasıl çıktığı. | — |
| `detail-scenario` | Senaryo ve Gerekçeler | Motorun bu araca neden bu riski verdiği. | — |
| `detail-assessment` | Ajan Değerlendirmesi bölümü | LLM ajanının bu kare için değerlendirmesi. | — |
| `detail-assess` | "Değerlendir / Yeniden değerlendir" | Bu kareyi LLM ajanına değerlendirtir. | — |
| `detail-reports` | Saha Raporları | Araca ait saha raporları ve doğrulama hükümleri. | — |
| `detail-distance` | Mesafe Geçmişi | Zamana göre üsse mesafe grafiği ve tablosu. | — |

## 3. Sık sorulan görevler (önerilen sıralar)

Aşağıdaki sıralar örnektir; kullanıcının sorusuna en uygun olanı seçin, gerekirse kısaltın ya da birleştirin.
Açıcı adımları (`sidebar-open`, `overlay-*`, `bottom-panel-toggle`) her zaman ekleyin; alan zaten açıksa arayüz
o adımı atlar.

- **Filtreleme / "filtre nasıl yapılır" / belirli riskteki araçları görme**:
  `sidebar-open` → `filter-risk` → `filter-vehicle` → `filter-scenario` → `filter-zone` → `sidebar-track-list`.
  Kullanıcı yalnızca risk derse `sidebar-open` → `filter-risk` → `sidebar-track-list`.
  Filtreleri sıfırlamak: `sidebar-open` → `filter-clear`.
- **Bir izi / aracı arama**: `topbar-search` → `sidebar-search` → `sidebar-track-list`.
- **Bir aracın detayını açma**: `sidebar-open` → `sidebar-track-list` → `detail-panel`.
- **Aracı izleme listesine alma**: `sidebar-open` → `sidebar-track-list` → `detail-watch` → `sidebar-watchlist`.
- **İzleme listesinden çıkarma**: `sidebar-open` → `sidebar-watchlist`.
- **Bildirimleri görme**: `topbar-notifications` → `notifications-panel`.
- **Aracı takip etme / haritada bulma**: `sidebar-open` → `sidebar-track-list` → `detail-follow` (ya da `detail-focus`).
- **Katmanları açıp kapatma**: `sidebar-open` → `sidebar-layers`.
- **Bir bölgeye gitme**: `sidebar-open` → `sidebar-zones`.
- **İzsiz tespitleri görme**: `sidebar-open` → `sidebar-untracked`.
- **Zamanı oynatma / geçmişe gitme**: `timeline-play` → `timeline-speed` → `timeline-slider`.
  Belirli bir olaya gitmek: `timeline-events`.
- **Rota çizimini değiştirme**: `map-trail-mode` (ya da `timeline-trail`).
- **3D görünüm**: `map-view-mode`. **Tam ekran**: `map-fullscreen`. **Haritayı sıfırlama**: `map-reset-view`.
- **En riskli / öncelikli araçlar**: `overlay-priority` → `priority-panel`.
- **Genel durum / özet**: `overlay-summary` → `summary-panel`.
- **Kareleri ajanla (LLM) toplu değerlendirme**: `overlay-summary` → `summary-assess-all`.
- **Tek bir aracın/karenin ajan değerlendirmesi**: `sidebar-open` → `sidebar-track-list` → `detail-assessment` → `detail-assess`.
- **Analist onayı / risk seviyesini elle belirleme**: `topbar-human-review` → `overlay-reviews` → `review-analyst`
  → `review-levels` → `review-note` → `review-submit`.
- **Son söz insanda özelliğini açma/kapama**: `topbar-human-review`.
- **Ajana soru sorma**: `overlay-chat` → `chat-input` → `chat-send`. Sesle sormak: `overlay-chat` → `chat-mic` → `chat-send`.
- **PDF tehdit raporu alma**: `topbar-pdf-report`.
- **Verileri yenileme**: `topbar-refresh`.
- **Sesli uyarıları açma/kapama**: `topbar-voice-alerts`.
- **Tüm izleri tablo olarak görme / sıralama**: `bottom-panel-toggle` → `explorer-search` → `explorer-filters` → `explorer-sort` → `explorer-table`.
- **Çelişkili saha raporları olan araçlar**: `bottom-panel-toggle` → `explorer-contradictions` → `explorer-table` → `detail-reports`.
- **Aracın üsse mesafesinin değişimi**: `sidebar-open` → `sidebar-track-list` → `detail-distance`.
- **Bir aracın neden riskli olduğu**: `sidebar-open` → `sidebar-track-list` → `detail-risk` → `detail-scenario`.

## 4. Yanıt biçimi (LLM için)

Yalnızca aşağıdaki JSON nesnesini döndürün; açıklama, markdown ya da kod bloğu eklemeyin:

```json
{
  "message": "Kullanıcıya gösterilecek tek cümlelik özet (Türkçe).",
  "steps": [
    {"id": "sidebar-open", "instruction": "Harita panelini açmak için buraya tıklayın."},
    {"id": "filter-risk", "instruction": "Görmek istediğiniz risk seviyesini seçin."}
  ]
}
```

- `steps` sıralıdır; kullanıcı her vurgulanan öğeye tıkladıkça bir sonrakine geçilir.
- `id` yalnızca bu belgedeki katalog ID'lerinden biri olabilir. ID uydurmayın.
- `instruction` kısa, emir kipinde, Türkçe bir cümledir ve kullanıcının o öğede ne yapacağını söyler.
- En fazla 8 adım kullanın; soruya yanıt veren en kısa sırayı seçin.
- Soru arayüz kullanımıyla ilgili değilse veya karşılığı yoksa `"steps": []` döndürün ve `message` içinde
  nedenini kısaca açıklayın.
- Konuşmadan metne çeviri hatalı olabilir ("filtre" yerine "filtreler", "fitre" gibi); en yakın anlamı seçin.
