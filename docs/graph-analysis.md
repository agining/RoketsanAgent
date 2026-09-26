# Oyun içi trajectory graph analizi

Bu modül hackathon oyununun tamamlanan hareket kayıtlarını analiz eder. Mevcut `threat` / `normal` alanları oyun varlıklarının etiketleridir. Çıktılar oyuncuya bölge incelemesi ve oyun içi gözlem sıklığı önerisi sunar; otomatik oyun emri uygulamaz. Gelecek zaman veya ertesi gün tahmini yapılmaz.

## Mevcut projeye bağlantı

Backend FastAPI, `app.service.Service`, `Analyzer`, `Dataset` ve mevcut LangChain ajanı üzerine kuruludur. `data/tracks.csv` → `Dataset.tracks` → graph; motor/LLM/oyuncu incelemesinin nihai etiketi → track sınıfı; `Dataset.reports` → kaynakla sınırlandırılmış rapor çıkarımı → graph metadata akışı kullanılır.

Frontend React + Zustand + MapLibre'dir. Graph kendi hook'u üzerinden mevcut API taşıma katmanını kullanır. Harita Paneli içindeki **Oyun içi graph analizini aç** düğmesi analizi başlatır. Mevcut track, playback, inceleme, sohbet ve rapor akışları aynı servisleri kullanmaya devam eder.

Etiketleme, mevcut sistemin **güncel nihai track etiketidir**. Graph bu etiketin geçmişteki her dakika için geçerli olduğunu iddia etmez. Seçilen aralık yalnızca hareket ve zaman bilgisi olan raporları sınırlar. Aynı track birden fazla gözlemde farklı nihai seviyelere sahipse yapılandırılan threat seviyelerinden herhangi birini almış olması track etiketini belirler. Sınıflandırılmamış track'ler sessizce normal kabul edilmez; `unclassified_trajectory_count` ile gösterilir ve oran hesabından çıkarılır.

## Dosyalar ve sorumluluklar

| Dosya | Sorumluluk |
| --- | --- |
| `app/graph/config.py` | Doğrulanan yarıçaplar, eşikler, ağırlıklar, metrik ölçekleri ve cache sınırı |
| `app/graph/models.py` | Düğüm, kenar, bölge, analiz sonucu ve Pydantic rapor şeması |
| `app/graph/geometry.py` | Yerel metre projeksiyonu ve yarıçapa göre spatial hash |
| `app/graph/paths.py` | STRtree ile gözlenen yol segmentlerinin kesişimleri |
| `app/graph/window.py` | Aynı günün oyun saati aralığına kırpma; sınırda interpolasyon |
| `app/graph/builder.py` | Ortak düğümler, yönlü graph'lar, tekil varlık ve geçiş sayımları |
| `app/graph/metrics.py` | Merkeziyetler, ham oran, baseline, lift ve gözlenen rota kullanımı |
| `app/graph/smoothing.py` | Bayesian shrinkage ve gözlem hacmi çarpanı |
| `app/graph/scorer.py` | Sabit ölçekli, deterministik skor ve bileşen katkıları |
| `app/graph/recommendations.py` | Oyun içi açıklamalar ve gözlem önerileri |
| `app/graph/extraction.py` | Metinde açık koordinat ve kesinlik kanıtlarını ayrıştırma |
| `app/graph/intelligence.py` | Mevcut LLM ile çıkarım, kaynak doğrulaması ve rapor eşleştirme |
| `app/graph/repository.py` | İçerik fingerprint'i ve atomik JSON yazımı |
| `app/graph/service.py` | Akışın orkestrasyonu ve veri/etiket/config/aralık bazlı cache |
| `app/graph/routes.py` | Graph REST endpointleri ve istek doğrulaması |
| `frontend/src/types/graph.ts` | Frontend graph sözleşmesi |
| `frontend/src/services/api.ts` | Graph istekleri dahil ortak taşıma katmanı |
| `frontend/src/services/graphAnalysisService.ts` | Gelen graph yanıtının çalışma zamanı doğrulaması |
| `frontend/src/hooks/useGraphAnalysis.ts` | İsteğe bağlı yükleme, iptal, yenileme ve hata durumu |
| `frontend/src/components/graph/GraphAnalysisPanel.tsx` | Zaman aralığı, sıralı bölgeler, açıklamalar ve skor dökümü |
| `frontend/src/components/graph/useGraphOverlay.ts` | MapLibre ranked region katmanı ve haritadan bölge seçimi |
| `frontend/src/components/graph/graph.css` | Mevcut tema değişkenlerini kullanan panel stilleri |
| `frontend/src/App.tsx`, `MapSidebar.tsx`, `OperationsMap.tsx` | Panelin ve graph katmanının mevcut ekrana bağlanması |
| `tests/test_graph.py` | Gerçek bağımlılıklar ile sentetik graph/API regresyon testleri |
| `frontend/src/services/graphAnalysisService.test.ts`, `frontend/tests/graph.spec.ts` | Sözleşme, GeoJSON ve tarayıcı akışı testleri |
| `requirements.txt`, `requirements-dev.txt` | Graph bağımlılıkları ve test kurulumu |

## Düğüm ve kenar modeli

1. Aralık dışındaki hareketler çıkarılır. Başlangıç/bitiş iki gözlem arasındaysa yalnızca gözlenen segment üzerinde interpolasyon yapılır; track dışına extrapolasyon yoktur.
2. Yol segmentleri yerel metre koordinatlarına taşınır. STRtree yalnızca kesişme adayı segmentleri karşılaştırır; tüm track çiftleri taranmaz. Kesilen veya ortak segmentlerin uç noktaları iki trajectory'ye de eklenir.
3. Noktalar yarıçapı metre cinsinden olan spatial hash ile snap edilir. Komşu hücre boyutu yarıçaptan üretilir; derece cinsinden sabit hücre veya yalnızca Ankara'ya özel sınırlar kullanılmaz. Koordinat sırası sabit olduğundan input track sırası sonucu değiştirmez. Küme merkezleri atama bittikten sonra hesaplanır; atama sırasında kayan centroid zincirlemesi yapılmaz.
4. Yalnızca tek varlığın kullandığı iç yol noktaları düğüm olmaktan çıkarılır. Track uçları ve en az iki varlığın paylaştığı spatial kümeler tutulur. Yolun iç geometrisi graph düğümü sayılmaz.
5. Ardışık anlamlı bölgeler arasında gözlenen yönlü geçişler kenardır. `G_all`, `G_normal`, `G_threat` aynı düğüm kimliklerini kullanır; alt graph'lar yalnızca ilgili sınıfın gerçekten ziyaret ettiği düğümleri içerir.

`total_vehicle_count`, `threat_vehicle_count`, `normal_vehicle_count`, `unique_vehicle_count` **tekil track sayısıdır**. Her biri aynı bölgeden tekrar geçse bile bir kez sayılır. `passage_count` tekrar girişleri, `point_count` atanan nokta örneklerini, kenar `total_weight` tekrar geçişleri ayrıca gösterir. Tekil araç oranları ile kenar kullanım ağırlıkları birbirine karıştırılmaz. Mevcut dataset bir track'i bir araç olarak tanımlar; farklı track ID'lerinin aynı fiziksel varlığa ait olduğu bilinmeden fiziksel araç birleştirmesi yapılmaz.

Yerel projeksiyon, bu projenin bölgesel oyun haritası içindir. Küresel, kutup veya tarih çizgisini geçen haritalar için projeksiyon katmanı değiştirilmelidir. Segment kesişimi geometrik yol paylaşımıdır; iki aracın aynı anda orada olduğunu veya üst geçitlerin aynı yükseklikte olduğunu kanıtlamaz.

## Metrikler ve skor

| Metrik | Tanım |
| --- | --- |
| In/out degree | Gözlenen yönlü giriş/çıkış bağlantısı sayısı |
| Degree centrality | `(in_degree + out_degree) / (2 * (N - 1))`; yönlü graph için `[0,1]` ölçeği |
| In/out centrality | İlgili degree / `(N - 1)` |
| Betweenness | NetworkX normalize edilmiş, ağırlıksız graph shortest-path betweenness |
| Weighted degree | Gelen + çıkan gözlenen geçiş ağırlıkları; shortest-path maliyeti olarak kullanılmaz |
| Alt graph centrality | `b * betweenness + (1-b) * degree`, `b` config üzerinden |
| Centrality gap | `threat_centrality - normal_centrality`; iki aktif graph kendi boyutunda normalize edilir |
| Baseline | Aralıktaki tekil threat track / sınıflandırılmış tekil track |
| Ham yerel oran | Düğümdeki tekil threat / tekil toplam |
| Ham lift | Ham yerel oran / baseline; baseline sıfırsa `0` |
| Düzeltilmiş oran | `(threat_count + C * baseline) / (total_count + C)` |
| Gözlenen önem | Düğümden geçen tekil threat track / aralıktaki bütün tekil threat track |
| Gözlem hacmi güveni | `n / (n + C)`; anomali skorundan ayrı gösterilir |

Shortest-path betweenness, gözlenen rota kullanımıyla ayrı tutulur. Büyük graph'larda `betweenness_sample_size` üzerinde sabit random seed ile örneklenir; küçük graph'larda tam hesaplama kullanılır. İzole/boş graph değerleri güvenli biçimde sıfırdır.

**Küçük örneklem yöntemi:** Varsayılan adaptive modda `C`, seçili aralıktaki bütün skorlama öncesi düğümlerin tekil araç sayılarının aritmetik ortalamasıdır. Tekrar geçişler sayılmaz. Bu, veri ölçeğine uyarlanan bir düzenlileştirme sezgisidir; öğrenilmiş optimum prior değildir ve mekânsal kümelenme ayarından etkilenir. Boş graph güveni sıfırdır. Gözlem hacmi güveni `n/(n+C)` ayrı gösterilir, skora tekrar çarpılmaz. `adaptive=false` sabit C ve eski hacim güveni ayarlarını kullanır. `min_observation_threshold` kısayolu bu sabit moda geçer. Güven bir doğruluk olasılığı veya confidence interval değildir.

Skorun lift bileşeni düzeltilmiş lift'i kullanır; API'deki `threat_lift` ham gözlenen lift'tir. Normalizasyonlar graph içindeki rastgele maksimumlara değil config ölçeklerine dayanır:

```
lift_component = clamp((smoothed_lift - 1) / (lift_saturation - 1), 0, 1)
gap_component = clamp(centrality_gap / centrality_gap_saturation, 0, 1)
anomaly_evidence = max(lift_component, gap_component)  # threat gözlemi yoksa 0
multiplier = anomaly_evidence
interest_score = sum(weight_i * normalized_component_i) * multiplier
```

Karşılaştırma aralığında yalnızca tek sınıf varsa `anomaly_evidence=0` kabul edilir; normal karşılaştırma verisi olmadan olağandışılık iddiası üretilmez. Self-loop seçeneği açıksa geçiş ve ağırlık sayımları bunu korur; merkeziyet normalizasyonunda self-loop komşu sayılmaz.

Diğer bileşenler düzeltilmiş oran, gözlenen rota kullanımı, threat graph merkeziliği ve metinde belirtilen rapor kesinliğidir. Ağırlıklar toplamı 1 olmalıdır; her bileşenin ham değeri, normalize değeri, ağırlığı ve nihai katkısı `score_breakdown.components` içinde vardır. Katkılar final skora toplanır. `graph_interest_score` ile `intelligence_contribution` bağımsız olarak döner. Rapor sayısı veya trafik hacmi tek başına yüksek skor oluşturmaz; bütün graph'ta aynı sınıf oranına sahip, pozitif yapısal fark göstermeyen bölgeler anomali sayılmaz.

## Raporlar ve mevcut LLM

Yeni LLM client veya entegrasyon oluşturulmaz. `Service.agent.llm` aynen kullanılır; mevcut `build_llm()` model, base URL, sağlayıcı ve thinking ayarlarını yönetmeye devam eder. Structured extraction bu nesneden oluşturulur. Testlerde LLM yerine yalnızca test double kullanılır; production sonucuna sahte rapor eklenmez.

- Rapor metni system mesajından ayrılmış, güvenilmeyen veri olarak gönderilir.
- Pydantic dünya koordinat sınırlarını ve enlem/boylam çiftini doğrular.
- Çıkarılan ID ve source kaynak kayıt tarafından belirlenir.
- Koordinatlar model yanıtına güvenilerek kullanılmaz: yalnızca kaynak metinde açıkça bulunan N/S/E/W veya `lat: ..., lon: ...` biçimleri kabul edilir.
- Modelin metinde bulunmayan yer adı, araç adı veya keyword'ü çıkarılır. Kaynak `official` olması güven düzeyi üretmez; metin kesinlik belirtmiyorsa confidence `null` olur.
- Konum adı için geocoding veya bütün sektöre kanıtsız yayılım yoktur. Konum adı var fakat açık koordinat yoksa rapor unmatched kalır.
- Zaman aralığı seçildiğinde zamanı bilinmeyen rapor spatial eşleştirmeye katılmaz; unmatched içinde korunur.
- LLM devre dışı veya çağrı hatalıysa kaynak metin/koordinatları koruyan deterministik extraction kullanılır; `extraction_method` bunu açıkça belirtir. Hatalı LLM çağrısının fallback'i başarılı LLM sonucu olarak cache'lenmez.
- İlk LLM hatasında aynı batch'in diğer raporları tekrar tekrar uzak çağrı yapmaz. Sonraki explicit recompute yeni batch başlatarak tekrar deneyebilir. Çağrı timeout'u mevcut structured runnable'a iletilir; sağlayıcının mevcut retry ayarı korunur.
- LLM özetinin bütün anlamsal iddiaları programatik olarak doğrulanamaz. Spatial eşleşme raporun doğrulandığı anlamına gelmez; kaynak metin ve rapor ID'leri inceleme için tutulur.

Raporlar spatial index ile en yakın düğüme, yapılandırılan yarıçapta eşlenir. Aynı ID düğüme tekrar eklenmez. Eşleşmeyen kayıtlar `no_explicit_coordinates`, `outside_node_radius`, `unknown_time` gerekçeleriyle API'de korunur.

## Bölge birleştirme

Bölge adayları skor ve sabit ID ile sıralanır; seed yarıçapı içindeki komşu düğümler tek bölge olur. Zincirleme genişlemeyle iki uzak ucu aynı bölgeye dönüştürmekten kaçınılır. Bölgenin araç/trajectory sayımları düğümlerdeki ID kümelerinin **union**'ıdır; toplam veya maksimum sayı kullanılmaz. Rapor ID'leri de tekilleştirilir.

Bölge skoru en yüksek skorlu temsil düğümüne aittir; `representative_node_id` ve skor dökümü bunu belirtir. Yerel bölge oranı birleşik tekil araçlardan hesaplanır; temsil düğümünün skor girdisiyle aynı olduğu iddia edilmez. Normal bölgeler `regions` içinde görünür; yalnızca eşiği geçenler `high_interest_regions` içinde yer alır. Yüksek bölge bulunmadığında en yüksek normal bölge sahte hotspot olarak terfi ettirilmez.

## API

Tüm analiz endpointleri `start_time=HH:MM` ve `end_time=HH:MM` kabul eder. Varsayılan tüm gözlenen aralıktır. Aynı gün, 00:00–23:59; başlangıç bitişten sonra veya saat biçimi geçersizse HTTP 422.

| Endpoint | Yanıt |
| --- | --- |
| `GET /api/graph-analysis` | Özet, normal bölgeler, high-interest bölgeler, aralık ve veri revision'ı |
| `GET /api/graph-analysis/regions?min_score=0.35&severity=YUKSEK` | Filtreli bölgeler |
| `GET /api/graph-analysis/regions/{region_id}` | Aynı aralıkta tek bölge; bulunamazsa 404 |
| `GET /api/graph-analysis/graph` | Düğümler, yönlü kenarlar, baseline ve revision |
| `GET /api/graph-analysis/unmatched-intelligence` | Eşleşmeyen yapılandırılmış raporlar |
| `GET /api/graph-analysis/config` | Varsayılan config; secret/model key içermez |
| `POST /api/graph-analysis/recompute` | Yeniden hesaplama sonucu; geçici özel config destekler |

Örnek gövde:

```json
{
  "force": true,
  "cluster_radius_m": 80,
  "min_observation_threshold": 15,
  "config": {
    "metrics": { "lift_saturation": 6, "centrality_gap_saturation": 0.25 }
  }
}
```

`config` bütün katmanları (weights dahil) override edebilir; verilmemiş alanlar varsayılanı kullanır. Flat iki alan varsa nested config'in üzerine uygulanır. Özel config yalnızca bu isteğe aittir; varsayılan config'i kalıcı değiştirmez. `force` graph hesaplamasını tekrarlar; değişmemiş başarılı LLM çıkarımları ayrıca tekrar çağrılmaz.

## Cache ve eşzamanlılık

Hareket noktaları, güncel nihai etiketler, rapor içeriği, config, aralık ve LLM modu/modeli içerik hash'ine katılır. Aynı aralık için tekrar aynı veri gelirse sonuç cache'den döner. Reload, oyuncu etiketi veya rapor metni değiştiğinde yeni revision hesaplanır. Cache bounded LRU'dur; servis kilidi eşzamanlı aynı işin tekrar hesaplanmasını önler. JSON atomik yazılır. Diskteki eski graph JSON'u güncel hesaplamanın yerine otomatik yüklenmez; teşhis/son çıktı kaydıdır.

## Çalıştırma ve test

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.api:app --reload --port 8000
```

Başka terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Backend regresyonları:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_graph.py -q
```

Frontend:

```powershell
cd frontend
npm test
npm run build
npm run test:e2e:install
npm run test:e2e
```

Chromium indirmek yerine mevcut Chrome kullanılacaksa test ortamına açık binary yolu verilebilir:

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
npm run test:e2e
```

Test fixture'ları yalnızca `tests/` altındadır. Graph testleri haricî LLM çağrısı yapmaz ve production output dosyalarını değiştirmez. Haritadaki ranked region işaretleri şematik piksel boyutudur; bir kapsama poligonu değildir, gerçek yarıçap region API'sindedir.


## Kayıtlı araç gerekçeleri

`Service.assessments` / `outputs/assessments.json` içindeki araç açıklamaları, geçerli karar ve track_id ile bölgelere bağlanır. Eski motor seviyesine ait değerlendirmeler, elenmiş araçlar ve seçili aralık dışında kalan değerlendirmeler kullanılmaz. Kayıtlar vehicle_id ile tekilleştirilir; aynı rota kayıtları bağımsız kanıt sayılmaz. İçerik değişiklikleri graph revision değerini değiştirir.

Bölge panelindeki özet düğmesi `POST /api/graph-analysis/regions/{region_id}/vehicle-summary` çağırır; aynı zaman parametreleri geçerlidir. Mevcut LLM ile Türkçe kaynak referanslı bulgular çıkarılır. Kaynakta olmayan araç referansları reddedilir; modelin metin doğruluğu garanti edilmez, kaynak açıklamalar panelde görülebilir. İçerik/model bazlı cache `graph_vehicle_summaries.json` dosyasındadır. LLM yoksa veya hata verirse kayıtlı gerekçeler gösterilir; eksik araç değerlendirmesi otomatik üretilmez. Özet, zaten sınıflandırmada kullanılan değerlendirmeleri ikinci kez sayısal kanıt olarak eklemez.


## Oyun içi grup yoğunluğu

Bölge birleştirmesinden sonra tekil track kümeleri üzerinden ayrı bir öncelik kuralı uygulanır. En az 3 tehdit rotası ve en az %50 yerel tehdit oranı Orta (skor alt sınırı 0.40); en az 4 tehdit rotası ve aynı oran Yüksek (alt sınır 0.65) üretir. 3 rotadan az bölgeler Orta eşiğinin altında tutulur. Tek araç tekrarları ve farklı düğümlerdeki aynı rota çoğaltılmaz. Bu bir oyun öncelik kuralıdır, istatistiksel anomali anlamlılığı veya birlikte hareket kanıtı değildir; eşzamanlılık ölçülmez. Normal araçlar oran hesabında kalır.

`group_concentration` katkısı temel skoru hedefe tamamlayan farktır; önceki skor üzerine hedef skorun tamamı eklenmez. Tekil araç sınırı uygulanırsa temel katkılar orantılı azaltılır. Katkılar final skora toplamaya devam eder. `group_rule` alanı gerekçeyi ve eşikleri taşır. Bölgeler güncellenmiş skora göre yeniden sıralanır; yüksek bölge filtresi ve harita aynı skoru kullanır. Temsilci düğüm metrikleri korunur; final skor artık bölgesel kuralı da içerir.
