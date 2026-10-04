# Kien Thuc Phong Van Ky Thuat Data Engineering & Bao Ve Kien Truc He Thong

Tai lieu nay ghi lai cac cau hoi phong van ky thuat, cau tra loi ban dau cua ung vien, cau tra loi chuan muc cua Senior Engineer, va he thong thuat ngu kien truc chuyen sau duoc duc ket tu Du an SEC Financial Data Pipeline & RAG System.

---

## 1. Kien Truc Luu Tru & Dinh Dang Du Lieu Dang Cot (Columnar Storage)

### Cau hoi phong van
> "Trong du an nay, du lieu di chuyen qua kien truc Medallion Lakehouse, chuyen doi cac cong bo HTML va JSON tho thanh tep Parquet nen Snappy tai cac tang Silver va Gold.
> 1. Tai sao ban lai chon Parquet thay vi CSV hoac JSON?
> 2. Duoi goc do luu tru vat ly tren dia va hieu nang truy van phan tich (OLAP), luu tru dang cot toi uu hoa Disk I/O va su dung CPU nhu the nao?"

### Cau tra loi goc & Truc giac ky thuat cua ung vien
- **Muc do thau hieu:** Parquet giup giam dung luong du lieu doc, tang toc do truy van phan tich, dat ty le nen cao hon, va cau truc dang cot giup tim gia tri nhanh hon ma ton it tai nguyen CPU hon.
- **Danh gia:** Truc giac ky thuat tot. Ly do cot loi (giam I/O va hieu qua nen) la hoan toan chinh xac. Can bo sung cac thuat ngu tieu chuan nganh (Column Projection va Predicate Pushdown).

### Cau tra loi chuan muc (Senior Engineering Model Answer)
> "Chung toi chon Apache Parquet thay vi cac dinh dang theo dong (CSV/JSON) vi 3 ly do kien truc:
> 
> Thu nhat, ve hieu qua luu tru: Parquet to chuc cac gia tri theo cot thay vi theo dong. Boi vi cac gia tri trong cung mot cot co chung kieu du lieu va thuong xuyen lap lai cac mau hinh (patterns), cac bo ma hoa nhu Dictionary Encoding va Run-Length Encoding (RLE) ket hop voi Snappy giup dat ty le nen dia hon 70% so voi JSON tho.
> 
> Thu hai, ve hieu nang doc phan tich (OLAP): Parquet ho tro **Column Projection (Chieu cot)**. Cac truy van phan tich hiem khi can doc toan bo tat ca cac cot. Voi Parquet, engine truy van nhay truc tiep den dung khoang byte tren dia cua cac cot duoc yeu cau (vi du: `ticker`, `word_count`) va bo qua hoan toan cac cot van ban tu su nang ne, giup giam Disk I/O tu 80-90%.
> 
> Thu ba, ve toi uu hoa nang luc tinh toan: Tep Parquet chua sieu du lieu (metadata) o phan cuoi tep (File Footer), ghi lai thong so thong ke `min` va `max` cho tung khoi du lieu (data block). Thong qua **Predicate Pushdown (Day vi tu xuong tang luu tru)**, cac truy van co bo loc nhu `WHERE year = 2026` chi can kiem tra footer va co the loai bo toan bo tep ma khong can doc du lieu dong vao bo nho RAM."

### Tu dien Thuat ngu Chuyen sau

#### Column Projection (Chieu cot)
- **Dinh nghia:** Kha nang cua dinh dang luu tru va query engine chi doc cac cot duoc chi dinh trong cau truy van (vi du: `SELECT ticker, word_count FROM table`) ma khong can nap cac cot khong can thiet tu dia.
- **Co che vat ly:** Trong cac tep theo dong (CSV/JSON), cac truong cua mot ban ghi nam lien tiep nhau tren dia (`val1, val2, val3\n`). Dau doc dia bat buoc phai quet qua toan bo dong de lay duoc truong cuoi cung. Trong Parquet, tat ca gia tri cua `col1` nam lien tuc trong mot Data Page, tiep theo do la `col2`. Reader chi can tinh toan offset byte va doc dung cac trang can thiet.

#### Predicate Pushdown (Day vi tu xuong tang luu tru)
- **Dinh nghia:** Ky thuat toi uu hoa trong do cac dieu kien loc (predicates, vi du: `WHERE ticker = 'NVDA'`) duoc danh gia ngay tai tang luu tru truoc khi du lieu duoc nap vao bo nho tinh toan.
- **Co che vat ly:** Moi tep Parquet chua mot footer `FileMetaData` luu tru thong tin ve column chunks, offset trang tu dien, va cac so lieu thong ke (`min_value`, `max_value`, `null_count`). Khi truy van thuc thi, engine doc footer truoc. Neu gia tri tim kiem nam ngoai khoang `[min, max]` cua mot khoi, khoi do se bi bo qua hoan toan ma khong can giai nen hay phan bo bo nho RAM.

#### Dictionary Encoding (Ma hoa tu dien)
- **Dinh nghia:** Ky thuat nen khong ton hao (lossless) thay the cac chuoi gia tri lap di lap lai bang cac khoa so nguyen nho.
- **Vi du:** Neu chuoi `'AAPL'` (4 bytes) xuat hien 1.000.000 lan trong mot cot, luu tho se ton 4 MB. Voi Dictionary Encoding, mot tu dien nho anh xa `0 -> 'AAPL'`, va cot chi can luu so nguyen `0` (thuong duoc dong goi trong 1-2 bits), giup giam hon 80% dung luong.

#### Run-Length Encoding (RLE)
- **Dinh nghia:** Thuat toan nen ghi nhan cac gia tri giong nhau xuat hien lien tiep thanh mot bo gia tri va so lan xuat hien.
- **Vi du:** Trong tap du lieu da sap xep co 10.000 dong lien tiep deu mang nam `2026`, RLE chi ghi nhan `(2026, 10000)`. Dieu nay bien hang chuc kilobyte thanh mot tuple so nguyen duy nhat.

#### Snappy Compression (Nen Snappy)
- **Dinh nghia:** Thuat toan nen dinh huong theo byte do Google phat trien, duoc thiet ke toi uu cho thong luong xu ly (throughput) thay vi ty le nen toi da.
- **Phan tich danh doi (Trade-off):** Cac thuat toan nhu Gzip hay Bzip2 cho ty le nen cao hon mot chut, nhung chu trinh giai nen cua chung ton rat nhieu CPU. Snappy co the giai nen voi toc do vuot 250-500 MB/s tren moi CPU core, dam bao qua trinh giai nen khong bao gio tro thanh nut that co chai (bottleneck) cua he thong pipeline.

---

## 2. Dieu Phoi Pipeline, Cam Bien & Tinh Kha Hoan (Idempotency)

### Cau hoi phong van
> "Bao cao Form 10-K duoc cac cong ty nop moi nam mot lan. Neu pipeline cua ban duoc lap lich tu dong chay vao luc 02:00 sang hang ngay:
> 1. Lam the nao de he thong xac dinh co bao cao moi hay khong ma khong phai tai xuong cac tep HTML khong lo hang chuc megabyte?
> 2. Tinh Kha hoan (Idempotency) co y nghia gi trong Data Engineering, va neu mot tac vu bi loi mang phai chay lai 3 lan, lam sao ban dam bao khong xay ra tinh trang trung lap du lieu?"

### Cau tra loi goc & Truc giac ky thuat cua ung vien
- **Muc do thau hieu:** Pipeline gui yeu cau nhe de kiem tra xem co bao cao moi khong, neu khong co gi thay doi thi dung lai khong chay cac buoc sau. Dinh nghia dung tinh kha hoan: *"Thuc hien mot thao tac nhieu lan van de lai trang thai he thong giong nhu chay lan dau tien."* Xac nhan rang cac tac vu thu lai khong lam duplicate du lieu.
- **Danh gia:** Nam rat vung dinh nghia toan hoc cua Idempotency ($f(f(x)) = f(x)$). Can lam ro co che ky thuat cu the: Dat ten mang tinh xac dinh (Deterministic Naming) va Ghi de nguyen tu (Atomic Overwrite).

### Cau tra loi chuan muc (Senior Engineering Model Answer)
> "De tranh lang phi tai nguyen trong cac lan chay tu dong 02:00 sang hang ngay, chung toi trien khai **Mau thiet ke Sensor va High-Water Mark** tai Buoc 3:
> 
> Thay vi tai tep HTML 8 MB, cam bien (sensor) chi phat mot request HTTP GET rat nhe den endpoint cua SEC EDGAR (`https://data.sec.gov/submissions/CIK{cik}.json`), lay ve goi JSON chi khoang 5 KB chua sieu du lieu. Sensor boc tach gia tri `accessionNumber` moi nhat va so sanh voi ban ghi luu trong `metadata.json` cuc bo. Neu accession trung khop, DAG se lap tuc ngat ngan (short-circuit) toan bo cac tac vu phia sau, hoan thanh kiem tra trong chua day 4 giay ma khong ton CPU hay token API.
> 
> Ve **Tinh Kha hoan (Idempotency)**, mot thao tac duoc coi la idempotent neu chay no 1 lan hay 10 lan deu tao ra trang thai he thong hoan toan nhu nhau. Trong pipeline nay, tinh kha hoan duoc bao dam nho **Deterministic Naming** va **Atomic Overwrite**:
> 
> Moi tep artifact dau ra deu mang duong dan khoa nghiep vu co dinh (vi du: `data/03_primary/chunks/NVDA_2026_chunks.parquet`). Neu su co mang khien mot task phai retry 3 lan, moi lan retry se ghi de truc tiep len chinh duong dan do. Boi vi chung toi khong bao gio gan timestamp gio chay vao ten file va tranh cac thao tac append-only khong co deduplication, tinh trang nhan doi ban ghi duoc triet tieu tuyet doi."

### Tu dien Thuat ngu Chuyen sau

#### Sieu du lieu (Metadata) vs. Du lieu noi dung (Payload)
- **Payload Data:** Noi dung thuc te cua tai lieu (vi du: toan bo van ban 8 MB Form 10-K HTML gom Item 1A, cac bang tai chinh va thuyet minh).
- **Metadata:** Du lieu mo ta noi dung (vi du: `filingDate: 2026-02-25`, `accessionNumber: 0001045810-26-000021`, ten file, va kich thuoc byte).
- **Chenh lech chi phi:** Lay metadata chi ton ~5 KB truyen tai va ~100 ms do tre; lay payload tho ton 2-8 MB va mat nhieu giay. Kiem tra metadata truoc la nguyen tac nen tang cua phat hien thay doi (Change Data Capture).

#### SEC Accession Number
- **Dinh nghia:** Ma dinh danh duy nhat gom 20 ky tu duoc he thong SEC EDGAR cap cho moi ho so do doanh nghiep nop len.
- **Cau truc:** `0000320193-25-000079`
  - `0000320193`: Central Index Key (CIK) cua cong ty (Apple Inc.).
  - `25`: Nam nop ho so (2025).
  - `000079`: So thu tu nop ho so do SEC cap trong nam do.
- **Vai tro ky thuat:** Dong vai tro khoa chinh tu nhien (natural primary key) va moc cao nhat (high-water mark) cho pipeline ingestion.

#### Sensor Pattern & Short-Circuit Execution
- **Sensor:** Mot tac vu tham do nhe nhang ma nhiem vu duy nhat la kiem tra dieu kien tien quyet ben ngoai (tinh san sang cua tep, thay doi version API, partition moi) ma khong chay xu ly nang.
- **Short-Circuit Execution:** Khi sensor tra ve `false` (khong co du lieu moi), DAG lap tuc dung hoac chuyen cac tac vu phu thuoc phia sau sang trang thai `SKIPPED`, tranh lang phi tai nguyen tinh toan.

#### Deterministic Naming vs. Non-Deterministic Timestamps
- **Tac hai cua Timestamp:** Neu pipeline dat ten file theo thoi gian chay (`chunks_20260911_020000.parquet`, `chunks_20260911_020015.parquet`), moi lan retry se sinh ra mot file moi tren o dia. Khi he thong phia sau doc `pd.read_parquet('chunks/')`, no se gop ca hai file va nhan doi ban ghi theo so lan retry.
- **Giai phap Deterministic:** Dat ten tep dua tren khoa nghiep vu bat bien: `{ticker}_{year}_chunks.parquet`. Du Task chay lai bao nhieu lan, no cung chi ghi vao dung mot file do. Tren dia luon luon chi co mot phien ban duy nhat.

#### Atomic Overwrite (Ghi de nguyen tu)
- **Dinh nghia:** Chien luoc ghi trong do phien ban moi cua tap du lieu thay the hoan toan phien ban cu trong mot buoc khong the bi chia cat, ngan ngua ghi dang do va khong lam tich luy ban ghi trung lap.

---

## 3. Tien Xu Ly Du Lieu Cho Generative AI & RAG

### Cau hoi phong van
> "Tai cac tang Gold va Curated, cac yeu to rui ro tu Item 1A duoc chia thanh cac cua so truot 500 tu voi 100 tu chong lap (overlap) truoc khi danh vector index vao ChromaDB.
> 1. Tai sao khong dua truc tiep toan bo bao cao Form 10-K vao Gemini AI ma phai chia nho (chunking) va lap index?
> 2. Co so ky thuat cua viec de 100 tu chong lap giua cac chunk la gi?"

### Cau tra loi goc & Truc giac ky thuat cua ung vien
- **Muc do thau hieu:** Dua ca tai lieu vao LLM la khong thuc te, lam tang do tre va chi phi API rat cao. Chuyen van ban thanh vector 384 chieu giup tim kiem do tuong dong chinh xac. 100 tu overlap giup giu duoc ngu canh va khong bi mat nghia o ranh gioi cac chunk.
- **Danh gia:** Hieu rat dung ve do tre, chi phi, so chieu vector va tinh lien tuc cua ranh gioi. Can bo sung cac thuat ngu AI Engineering chinh quy (Context Window economics, Hien tuong Lost in the Middle, Boundary Truncation).

### Cau tra loi chuan muc (Senior Engineering Model Answer)
> "Chung toi khong truyen truc tiep toan bo bao cao Form 10-K vao LLM vi 3 ly do kien truc:
> 
> Thu nhat, **Rang buoc ve Chi phi va Do tre:** Mot bao cao 10-K hoan chinh dai tu 50.000 den 100.000 tu. Dua toan bo van ban vao moi cau hoi cua nguoi dung se lam tieu ton luong token khong lo va gay ra do tre phan hoi keo dai hang chuc giay.
> 
> Thu hai, **Hien tuong 'Lost in the Middle':** Nghien cuu chi ra rang khi LLM xu ly context window qua lon, co che chu y (self-attention) cua mo hinh bi suy giam doi voi cac thong tin nam o giua van ban dai. Chung ghi nho thong tin o dau va cuoi prompt tot hon nhieu so voi cac doan o giua. Truy xuat vector giup co lap dung Top 5 doan van ban phu hop nhat, giu cho ngu canh prompt luon co dac va giam thieu ao giac (hallucination).
> 
> Thu ba, ve **100 tu chong lap (Context Boundary Preservation):** Viec cat van ban tuy tien (vi du: cat dung 500 tu mot cach co hoc) rat de chia doi mot luan diem phap ly hoac mot mo ta rui ro ra hai nua. Chunk dau tien se bi mat cau ket luan, con chunk thu hai bi mat phan tien de mo dau. Cua so chong lap 100 tu dam bao rang moi doan van hoac luan diem tron ven deu nam tron ven trong it nhat mot chunk."

### Tu dien Thuat ngu Chuyen sau

#### Context Window & Token Economics
- **Context Window:** So luong token (tu/sub-word) toi da ma mot Large Language Model co the nhan va sinh ra trong mot lan goi inference.
- **Goc do kinh te:** Mac du cac mo hinh hien dai (nhu Gemini) co context window rat lon (1 trieu+ tokens), chi phi duoc tinh tren tung token dau vao. RAG giup giam kich thuoc prompt tu 100.000 tokens xuong duoi 2.500 tokens moi truy van, giam hon 95% chi phi van hanh API.

#### Hien tuong "Lost in the Middle"
- **Dinh nghia:** Mau hinh hanh vi duoc quan sat trong kien truc Transformer self-attention, trong do mo hinh the hien kha nang truy hoi vuot troi cho cac du kien o hai dau prompt, nhung lai de bo quen cac thong tin nam sau o giua context.
- **Giai phap qua RAG:** Thay vi dua 100 trang tai lieu, RAG chi trich xuat 5 doan van 500 tu co gia tri nhat va dua gon gang vao prompt.

#### Semantic Chunking (Cat doan theo ngu nghia)
- **Dinh nghia:** Qua trinh chia van ban tu su thanh cac doan doc lap, tron ven ve mat y nghia nham toi uu hoa bieu dien cua model embedding.
- **Kich thuoc cua so:** Chunk qua nho (50 tu) se thieu ngu canh de dien ta cac rui ro tai chinh phuc tap. Chunk qua lon (2.000 tu) se lam loang vector embedding, khien cac khai niem bi mo nhat. Cua so 500 tu tuong ung rat tot voi 1-2 luan diem rui ro kinh doanh cu the.

#### Context Boundary Preservation (Cua so chong lap)
- **Co che:**
  ```text
  Van ban goc: [ ... Cau A. Cau B. Cau C. Cau D. Cau E. ... ]
  
  Chunk 1:     [ ... Cau A. Cau B. Cau C. ]
                               |---- 100 tu overlap ----|
  Chunk 2:                     [ Cau B. Cau C. Cau D. Cau E. ... ]
  ```
  Neu Cau C chua luan diem rui ro trong tam, no se xuat hien tron ven trong ca Chunk 1 va Chunk 2, ngan chan hien tuong dut gay ngu nghia vector.

#### Dense Vector Embeddings & Cosine Similarity
- **Dinh nghia:** Bieu dien van ban duoi dang toa do so trong khong gian vector nhieu chieu.
- **Model su dung:** `sentence-transformers/all-MiniLM-L6-v2` tao ra vector 384 chieu cho moi chunk.
- **Cosine Similarity:** Do goc cosin giua hai vector:
  ```text
  Cosine_Similarity = (u . v) / (||u|| * ||v||)
  ```
  Cac cau hoi ve "chuoi cung ung" tinh do tuong dong voi 262 vector cua cac chunk, tra ve cac doan noi ve thieu hut chip, thoi gian giao hang ma khong can phai trung khop tu khoa chinh xac.

---

## 4. Nhung Diem Cot Loi Khi Tra Loi Phong Van Ky Thuat

1. **Tap trung vao Su Danh Doi (Trade-offs):** Khong bao gio khen mot cong nghe la "tot" hay "nhanh" mot cach chung chung. Hay giai thich ban da danh doi dieu gi (vi du: *"Snappy chap nhan ty le nen thap hon mot chut de doi lay toc do giai nen 500 MB/s tren CPU"*).
2. **Neo vao Tinh Kha Hoan (Idempotency):** Bat ky pipeline nao cung co the chay thanh cong tren "con duong mau hong" (happy path). Cac ky su cap cao quan tam den dieu gi xay ra khi loi, khi retry va khi bi kich hoat trung lap. Luon nhan manh Deterministic Naming va Atomic Overwrite.
3. **Chat Luong Du Lieu La Tren Het:** Nhac den Quality Gates truoc khi noi ve Machine Learning hay LLMs. Du lieu sach va duoc kiem tra toan ven la dieu kien tien quyet de AI dua ra ket qua tin cay.

---

## 5. Ky Thuat He Thong Nang Cao: Dinh Danh Chunk, Danh So Thu Tu & Xu Ly Ban Ghi Mo Coi

### Cau hoi phong van
> "Khi pipeline chia nho tai lieu thanh cac chunks, lam the nao he thong dam bao viec danh so luon bat dau lai tu `0001` trong moi lan chay lai thay vi nhay len `0002` hay `0046`?
> Ngoai ra, dieu gi xay ra neu van ban goc co su thay doi nho giua cac lan chay (vi du: bao cao 10-K/A sua doi hoac ban sua loi lam sach text) khien so luong chunk bi co lai? Lam the nao ban ngan chan cac vector cu, loi thoi con sot lai trong Vector Database?"

### Cau tra loi goc & Truc giac ky thuat cua ung vien
- **Muc do thau hieu:** Nhan ra danh so bat dau lai tu `0001` la do co che dem khong luu trang thai, va nhan thuc duoc neu van ban thay doi giua hai lan chunking thi se de tao ra ban ghi trung lap neu khong quan ly tot.
- **Danh gia:** Cham dung cac thach thuc nen tang ve trang thai phan tan va vo hieu hoa cache: Vong lap phi trang thai (Stateless) vs Bo dem co trang thai (Stateful), va hien tuong Ban ghi Mo coi (Orphan Records).

### Cau tra loi chuan muc (Senior Engineering Model Answer)
> "Chung toi giai quyet tinh nhat quan cua chi muc va su troi dat du lieu bang 2 nguyen ly kien truc tach roi:
> 
> Thu nhat, ve **Tinh Nhat quan cua Chi muc (Tai sao retry luon bat dau tu `0001`):**
> Co che gan index hoan toan **Phi trang thai (Stateless)**. Thay vi dua vao bo dem co trang thai cua database (nhu cot `AUTO_INCREMENT` hay bien dem global), pipeline su dung generator cuc bo trong bo nho:
> ```python
> for idx, text in enumerate(raw_chunks, start=1):
>     chunk_id = f'{ticker}_{year}_RF_{idx:04d}'
> ```
> Moi khi `chunk_for_rag` thuc thi, ham tao ra mot danh sach cac doan cat moi trong RAM. Con tro `enumerate` luon khoi tao tai `1` cho phan tu dau tien. Vi vong lap khong luu bat ky trang thai nao qua cac lan chay tien trinh, nen chunk dau tien cua Nvidia 2026 luon mang nhan `NVDA_2026_RF_0001` mot cach xac dinh.
> 
> Thu hai, ve **Troi Dat Du Lieu (Text Drift) va Bai toan Ban Ghi Mo Coi (Orphan Records):**
> Dieu gi xay ra neu mot bao cao sua doi hoac ban fix lam thay doi van ban?
> - **Kich ban A (Noi dung doi, So luong chunk khong doi):** Neu van giu nguyen 45 chunks, lenh `upsert(id=chunk_id)` se ghi de truc tiep van ban va vector moi len chinh khoa chinh do.
> - **Kich ban B (Van ban bi co ngan / Dich chuyen ranh gioi):** Neu van ban bi rut ngan khien lan chay truoc sinh ra 45 chunks (`0001` den `0045`), nhung lan chay sau chi sinh 40 chunks (`0001` den `0040`), mot thao tac upsert don thuan se tao ra **Orphan Records**: cac chunks `0041` den `0045` cua lan chay truoc van nam lai trong Vector Database thanh 'vector ma', lam sai lech ket qua tim kiem.
> 
> De triet tieu vinh vien cac ban ghi mo coi, chung toi ap dung **Mau Partition Purge (Xoa sach theo phan vung)**:
> Truoc khi nap cac chunk sua doi cua mot cong ty, pipeline thuc hien mot lenh xoa co pham vi:
> ```python
> collection.delete(where={'$and': [{'ticker': ticker}, {'year': year}]})
> ```
> Lenh nay quet sach toan bo vector cu cua dung cap `(ticker, year)` do, dam bao cac chunk du thua bi xoa bo hoan toan truoc khi dua vector moi vao."

### Tu dien Thuat ngu Chuyen sau

#### Stateless Enumeration vs. Stateful Sequence Counters
- **Stateful Counter (`AUTO_INCREMENT` / Sequence):** Trang thai co so du lieu dung chung theo doi ID cao nhat da cap. Neu Run 1 chen 45 dong roi loi, Run 2 se bat dau cap ID tu `46`. Dieu nay pha vo tinh xac dinh cua primary key va tao ra ID khong kha hoan qua cac lan thu.
- **Stateless Loop (`enumerate`):** Phep lap trong bo nho cuc bo tren danh sach thu tu co vi tri khoi dau co dinh luc runtime. No dam bao chuoi ID sinh ra la dong nhat bat ke chuong trinh da chay lai bao nhieu lan truoc do.

#### Orphan Records (Ban ghi mo coi / Ghost Vectors)
- **Dinh nghia:** Cac ban ghi cu con sot lai trong database khi thuc the nguon duoc cap nhat sinh ra it don vi dau ra hon lan chay truoc.
- **Anh huong len Vector Search:** Neu khong duoc cat tia, vector search van se truy xuat cac chunk loi thoi nay, dua thong tin sai lech hoac da bi huy bo vao prompt LLM gay ra ao giac.

#### Partition Purge Pattern (Xoa sach theo phan vung)
- **Dinh nghia:** Thao tac don sach tat ca ban ghi thuoc ve mot phan vung logic (vi du: cong ty va nam tai chinh) ngay truoc khi ghi de tap du lieu moi.
- **Cai dat:** `collection.delete(where={'ticker': 'NVDA', 'year': 2026})` theo sau boi `collection.add(...)`. Lenh nay giu nguyen vector cua cac cong ty khac (AAPL, MSFT) trong khi bao dam tinh nhat quan tuyet doi cho doi tuong dang xu ly.

#### Content Hashing (Dinh danh mat ma qua SHA-256)
- **Giai phap thay the cho Sequential ID:**
  ```python
  import hashlib
  content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
  chunk_id = f'{ticker}_{year}_{content_hash}'
  ```
- **Co che:** Chunk ID duoc sinh truc tiep tu ma bam mat ma cua van ban.
- **Loi ich:**
  1. Neu van ban khong doi: Ma hash trung khop, bo qua viec re-embedding ton kem.
  2. Neu van ban thay doi du chi 1 ky tu: Ma hash thay doi hoan toan, giup phat hien thay doi va troi dat tuc thi.

---

## 6. He Thong Truy Xuat Nang Cao: Dense vs. Sparse, Bay Tu Vung & Reciprocal Rank Fusion (RRF)

### Cau hoi phong van
> "Tai sao tim kiem Dense Vector Search don le thuong kem hieu qua tren cac ho so tai chinh nhu Form 10-K?
> He thong cua ban ket hop BM25 va vector embedding nhu the nao, va tai sao ban lai chon Reciprocal Rank Fusion (RRF) thay vi phep cong diem tuyen tinh thong thuong?"

### Truc giac ky thuat cua ung vien
- **Muc do thau hieu:** Vector embedding anh xa y nghia vao khong gian ngu nghia, rat tot cho viec dien dat lai (paraphrase) nhung lai yeu khi can tim cac ma dinh danh chinh xac (ma co phieu, cac dieu khoan phap ly nhu EAR99, Item 1A).
- **Su can thiet cua Hybrid:** Ket hop tan suat tu khoa (BM25) voi vector ngu nghia giup bao quat ca do chinh xac ve tu ngu (lexical precision) va do bao phu ve ngu nghia (semantic recall).
- **Thach thuc khi hop nhat:** Cosine similarity (nam trong khoang 0 den 1) khong the cong truc tiep voi diem so BM25 khong gioi han (vi du: tu 0 den 25+) ma khong lam meo mo thu hang. Do do, hop nhat dua tren thu hang (RRF) la giai phap toan hoc vung chac nhat.

### Cau tra loi chuan muc (Senior Engineering Model Answer)
> "Trong bai toan truy xuat thong tin tai chinh, Dense Semantic Search don le bieu lo hai diem yeu chi mang:
> 
> 1. **Bay Tu Vung (The Lexical Trap) & Pha Loang Thuc The:** Cac mo hinh embedding nen 500 tu vao mot vector co dinh 384 chieu. Cac thuat ngu chuyen nganh hiem, cac ma quy dinh phap luat (vi du: 'EAR99 export regulations', 'Item 1A') va cac chi so ke toan bi pha loang tren cac chieu ngu nghia chung. Mot truy van ve 'rang buoc san xuat TSMC' co the tra ve cac doan ban ve chat ban dan noi chung nhung lai bo sot dung chunk co ten rieng cua nha may.
> 2. **Tu Ngoai Tap Tu Vung (Out-of-Vocabulary - OOV) & Tinh Nhay voi Tu Viet Tat:** Vector search thuan tuy thuong gap kho khan voi cac tu viet tat tai chinh dac thu hoac cac ma dinh danh phap ly moi chua xuat hien nhieu trong tap du lieu tien huan luyen (pre-training corpora).
> 
> De giai quyet triet de, he thong chung toi trien khai **Hybrid Retrieval ket hop Reciprocal Rank Fusion (RRF)**:
> - **Nhanh Sparse (BM25):** Tinh toan tan suat xuat hien cua tu va do hiem cua tu (bien the TF-IDF) tren toan bo kho chunks Parquet, dam bao do truy hoi cao cho cac token chinh xac, ma co phieu va dieu khoan luat dinh.
> - **Nhanh Dense (ChromaDB + SentenceTransformers):** Nam bat cac moi quan he khai niem khi cac tu khac nhau mang chung ban chat tai chinh (vi du: 'thieu hut chip' tuong dong voi 'thieu hut nang luc san xuat tai nha may').
> - **Hop nhat Thu hang (RRF):** Thay vi co gang chuan hoa cac thang diem khac nhau, RRF gop cac ung vien thuan tuy dua tren vi tri thu hang (ordinal rank) cua chung trong tung danh sach truy xuat:
> 
> ```text
> RRF_Score(d) = sum_{m in M} ( 1 / (k + rank_m(d)) )
> ```
> 
> trong do `k = 60` la hang so lam min, `M = {Dense, BM25}`, va `rank_m(d)` la thu hang bat dau tu 1 cua tai lieu `d` trong he thong `m`.
> 
> Cac tai lieu xuat hien o vi tri dau cua ca hai he thong se nhan duoc diem so RRF tich luy cao nhat. Co che nay xoa bo vinh vien **Bai toan Lech Thang do Diem so (Score Calibration Problem)** ma khong can den cac model Cross-Encoder ton kem."

### Tu dien Thuat ngu Chuyen sau

#### Cong thuc Okapi BM25
- **Inverse Document Frequency (IDF):**
  ```text
  IDF(q_i) = ln( (N - n(q_i) + 0.5) / (n(q_i) + 0.5) + 1.0 )
  ```
  Giam diem cac tu xuat hien pho bien khap noi trong cac bao cao 10-K (nhu 'company', 'fiscal', 'operations') trong khi tang diem theo cap so nhan cho cac tu hiem (nhu 'EUV', 'TSMC', 'ASML').
- **Cong thuc tinh diem:**
  ```text
  Score(D, Q) = sum_{i=1}^n ( IDF(q_i) * ( f(q_i, D) * (k1 + 1) ) / ( f(q_i, D) + k1 * (1 - b + b * (|D| / avgdl)) ) )
  ```
  Trong do `k1 = 1.5` kiem soat do bao hoa cua tan suat tu va `b = 0.75` dieu tiet do dai cua tai lieu.

#### Bai Toan Lech Thang Do Diem So (Score Calibration Dilemma)
- **Van de:** Dense retrieval sinh ra Cosine Similarity nam trong doan `[0, 1]`, trong khi BM25 cho ra diem so khong chan tren `[0, vô cùng)` phu thuoc vao do dai cau hoi va thong ke kho van ban.
- **Su that bai cua Phep cong Tuyen tinh:** Cong thuc `Score = a * Score_dense + (1 - a) * Score_bm25` that bai vi phuong sai phan phoi cua BM25 thay doi kho doan giua cau hoi ngan va cau hoi dai.
- **Giai phap cua RRF:** RRF chi dua vao vi tri thu hang `(1, 2, 3, ...)`. Dong gop toi da cua mot he thong truy xuat vao mot tai lieu bi chan tren boi `1 / (k + 1) = 1 / 61 ≈ 0.01639`, ngan khong cho bat ky he thong nao ap dao hoan toan bang diem so ao.
