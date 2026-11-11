# UI Redesign Notes

File nay gom cac diem phat sinh can trao doi hoac can ban kiem tra thu cong
trong qua trinh redesign frontend theo tung tab.

## Luot 1 - Nen tang UI

Trang thai:
- Da tao shell responsive, sidebar desktop collapse va mobile drawer.
- Da them route state cho `home`, `single`, `projects`, `series`,
  `seriesHistory`, `generate`, `settings`, `intro`, `guide`, `disclaimer`,
  `admin`.
- Da giu logic page hien co; chua redesign sau noi dung tung tab.

Can trao doi/kiem tra:
- `home` va `single` hien dang dung chung `ExplorePage` cu. Se tach that su o
  luot Trang chu va Sinh don.
- `projects` va `seriesHistory` hien la placeholder co chu dich de test route,
  se thay bang UI that o luot 4 va luot 6.
- `graphify update .` da cap nhat `graphify-out/graph.json` va
  `graphify-out/GRAPH_REPORT.md`; `graph.html` bi bo qua vi graph co hon 5000
  nodes. Neu can HTML viz, can tang `GRAPHIFY_VIZ_NODE_LIMIT` hoac giam input.

Manual checklist:
- Desktop: sidebar collapse/expand khong lam noi dung tran ngang.
- 320/375/414 px: bam `Menu`, dong drawer bang backdrop va nut dong.
- Tablet 768 px: menu mobile hien dung, button khong wrap.
- Route: `/single`, `/projects`, `/series`, `/series-history` load dung mat.

## Luot 1a - Dieu chinh Lich su chung

Trang thai:
- Da chot khong tach `Du an kich ban` va `Lich su series` thanh 2 tab rieng.
- Sidebar dung mot tab `Lich su`.
- `/projects` alias sang `Lich su` filter `Sinh don`.
- `/series-history` alias sang `Lich su` filter `Chuoi video`.

Can theo doi:
- Ten bien `apiKey` trong mot so component dang bao gom ca Gemini key va App
  API flow lich su. Chua doi trong luot nay de tranh pha logic cu.
- Ghi chu cu: ban dau `HistoryPage` dung API hien co. Luot sau da chuyen sang
  backend endpoint gom `/api/v1/history` de sort/paginate dung tren ca Project
  va SeriesV2.

Manual checklist:
- Filter `Tat ca / Sinh don / Chuoi video` khong wrap tai 320/375/414/768 px.
- Mo project sinh don: project da sinh sang output, project con goi y quay ve
  `Sinh don`.
- Mo series: sang `Chuoi video` va chon dung series.
- Breadcrumb `Series > ten series`: bam `Series` ve `Lich su` filter series.

## Luot 2 - Lich su chung backend-gop

Trang thai:
- Da them endpoint read-only `/api/v1/history?kind=all|single|series&skip=0&limit=20`.
- Da giu delete/open qua endpoint cu: project dung `/production/project/{id}`,
  series dung `/series/{id}`.
- Desktop/tablet `>=768px` dung pagination so; mobile `<768px` dung `Tai them`.

Phat sinh/can theo doi:
- Bug mat project sinh don den tu `listProjects()` cu: backend tra
  `{items,total}` nhung frontend doc nhu array. Da unwrap trong `api.ts`.
- Filter `Tat ca` neu chi gop frontend se sai thu tu global khi 2 endpoint co
  pagination rieng, nen chon backend union de co mot nguon sort duy nhat.
- `/history` khong tra raw `script_output`, `series_bible`, `season_map`,
  prompt hay artifact nang; chi tra preview/meta gon.

Manual checklist:
- `Tat ca / Sinh don / Chuoi video`: count dung va segment khong wrap tai
  320/375/414/768/desktop.
- Desktop: `Truoc`, so trang rut gon, `Sau` doi trang dung.
- Mobile: `Tai them` append tiep items, doi filter reset ve page dau.
- Project sinh don xuat hien lai trong lich su va mo dung trang theo status.

## Luot 3 - Trang chu

Trang thai:
- Da tach `HomePage` rieng khoi `ExplorePage`.
- Trang chu hien status App key/Gemini key theo state hien co, khong tu ping
  key khi vao trang.
- Da them shortcut `Sinh don`, `Chuoi video`, `Lich su`, `Cai dat`.
- Da them panel nhap dang mo va topic quick start toi da 3 item.

Phat sinh/can theo doi:
- Home chi biet key invalid neu lan luu/kiem tra gan nhat tra loi. Neu key het
  han sau do, can vao `Cai dat` hoac goi API khac moi lo loi.
- `Sinh don` van dung `ExplorePage` cu trong luot nay; chua redesign dense
  workflow cua tab do.

Manual checklist:
- `/` khong con render `ExplorePage`.
- Missing/invalid key hien alert va nut `Mo Cai dat`.
- Shortcut dung tab, khong reset draft khi bam `Sinh don`.
- Topic click set topic input roi sang `Sinh don`.
- 320/375/414/768/desktop khong tran ngang, nhan button khong wrap.

## Luot 3a - Trang chu gon sau review

Trang thai:
- Da bo panel `Viec dang mo` vi no chi phan anh state trong phien hien tai,
  khong tu khoi phuc sau refresh.
- Da bo `Chu de nhanh` de Home khong trung voi luong Sinh don.
- Da bo banner `San sang`; key da luu chi hien nhe trong status card.

Quyet dinh:
- Muon mo lai viec cu thi dung tab `Lich su`.
- Home khong auto-load project gan nhat va khong goi API moi.

Manual checklist:
- `/` khong con chu `Viec dang mo`, `Chu de nhanh`, `San sang`.
- Shortcut `Sinh don / Chuoi video / Lich su / Cai dat` van dung tab.
- Missing/invalid/validating key van hien alert va nut `Mo Cai dat`.

## Luot 3b - Home polish hierarchy

Trang thai:
- Da lam `Sinh don` thanh command chinh tren Home; `Chuoi video` la command
  phu, `Lich su` va `Cai dat` compact hon.
- Da doi strip cau hinh header sang dang nhe hon va hien `vi` thanh
  `Tieng Viet`.
- Da chan Home va cac tab khac fetch topic ngam; chi tab `Sinh don` moi truyen
  key that vao `useTopics`.

Quyet dinh:
- Home chi polish hierarchy, khong them tinh nang va khong auto-load du lieu
  lich su/topic.
- Khong dung gradient/orb/anh cho primary command.

Manual checklist:
- `/` nhin thay `Sinh don` la hanh dong uu tien dau tien.
- Vao Home khong goi topic API; sang `Sinh don` moi load topic.
- 320/375/414/768/desktop khong tran ngang, command khong wrap.

## Luot 3c - Home metadata trim

Trang thai:
- Da bo chip `Thoi luong` khoi header Home.

Quyet dinh:
- `Thoi luong` van giu trong `Cai dat` va workflow sinh; Home chi hien
  model va ngon ngu de gon hon.

## Luot 4 - Sinh don V2

Trang thai:
- Da doi `ExplorePage.tsx` thanh `SinglePage.tsx` va route `single` van giu
  nguyen.
- Da bo UI chon che do, chu de hot, YouTube URL va cau noi tao series khoi
  tab Sinh don.
- Luong tao moi luon gui `input_type=manual`; `generation_mode` duoc suy ra
  tu so canh: `<=20` la `single`, `>20` la `longform`.
- Da them `scene_duration_sec` vao request sinh goi y de backend luu vao cot
  `scene_duration` san co.

Phat sinh/can theo doi:
- Backend van giu `topic` va `youtube_url` de mo project cu va de Admin topics
  khong bi anh huong.
- History backend hien tinh moi row `Project` la `Sinh don`, nen project
  legacy co `series_short/series_long` van co the duoc mo vao tab Sinh don.
  UI se hien canh bao va khoa CTA sinh output cho cac row nay.
- Neu sau nay muon tach sach legacy series project khoi History `Sinh don`,
  can sua query `/api/v1/history` loc `Project.generation_mode` theo
  `single/longform/null`.

Manual checklist:
- Sinh don khong goi API topics khi vao tab.
- 320/375/414/768/desktop khong tran ngang; nut CTA khong wrap.
- Sinh goi y voi 20 canh gui `single`; 25 canh gui `longform`.
- Restore project gan day dung input, suggestion va output.

## Luot 4a - Sinh don 3 giai doan

Trang thai:
- Da khoi phuc stepper 3 giai doan `Khoi tao / Chon goi y / Sinh chi tiet`
  trong tab Sinh don.
- Phase `Khoi tao` chi hien nhap y tuong, cau hinh va gan day.
- Sau khi bam `Sinh goi y`, phase khoi tao bien mat; man hinh chi hien
  loading hoac danh sach goi y va strip xac nhan sinh chi tiet.

Quyet dinh:
- `Quay lai sua y tuong` giu input/cau hinh hien tai nhung xoa project,
  suggestions va output tam cua lan sinh goi y.
- `Reset` van xoa sach nhu cu.
- Output chi tiet van nam o `ProductionPage`, khong nhung vao tab Sinh don.

Manual checklist:
- Phase 1 khong tran ngang o 320/375/414/768/desktop.
- Bam `Sinh goi y` thi textarea/cau hinh/gan day bien mat.
- Chon mot goi y thi hien strip `Sinh chi tiet` va nut CTA khong wrap.
- Bam CTA sang output dung; back tu output ve Sinh don khong loi.

## Luot 4b - Sinh don style va layout can doi

Trang thai:
- Da them lua chon `Tuy chon` vao `Phong cach dung`.
- Khi chon preset, input `Phong cach tuy chinh` bi vo hieu hoa va custom cu
  duoc xoa de khong gui ngam.
- Khi chon `Tuy chon`, input custom duoc bat va bat buoc co noi dung truoc
  khi sinh goi y.
- Da thu gon header Sinh don con title va metadata nho.
- Da dua `Gan day` thanh section full-width ben duoi hang nhap y tuong/cau
  hinh; desktop hien thanh grid ngang.
- Da can hang tren de panel `Y tuong kich ban` va `Cau hinh` cao bang nhau.

Manual checklist:
- Chon preset thi custom disabled, placeholder ro rang.
- Chon `Tuy chon` nhung de trong thi hien loi truoc khi goi API.
- Restore project custom thi selector hien `Tuy chon`.
- Desktop: recent rong ngang; y tuong/cau hinh can chieu cao.
- 320/375/414/768: khong tran ngang, nut khong wrap.

## Luot 4c - Sidebar Sinh don ve khoi tao

Trang thai:
- Bam `Sinh don` trong sidebar luon dua workflow ve phase `Khoi tao`, ke ca
  khi dang o tab khac, phase chon goi y, hoac output.
- Da them guard bo qua response sinh goi y cu neu nguoi dung quay ve khoi tao
  trong luc request dang chay.

Manual checklist:
- O phase `Chon goi y`, bam sidebar `Sinh don` thi ve `Khoi tao`.
- O `ProductionPage`, bam sidebar `Sinh don` thi ve `Khoi tao`.
- Neu dang loading sinh goi y roi bam sidebar `Sinh don`, ket qua cu khong
  tu day UI quay lai phase `Chon goi y`.

## Luot 4d - Sidebar Sinh don reset mac dinh

Trang thai:
- Bam `Sinh don` trong sidebar bay gio reset sach ve trang thai ban dau thay
  vi giu lai y tuong/cau hinh cu.
- Reset mac dinh xoa input, project, suggestions, output tam, loi/loading va
  dua style ve `Anime`, ti le `16:9`, giay/canh `8s`.
- Da them reset revision de local UI `Phong cach dung` trong `SinglePage`
  cung quay ve preset mac dinh khi tab dang duoc mount.

Manual checklist:
- Nhap y tuong bat ky, bam sidebar `Sinh don`: textarea phai rong.
- Dang o phase `Chon goi y`, bam sidebar `Sinh don`: ve `Khoi tao` rong.
- Chon `Tuy chon`, nhap custom, bam sidebar `Sinh don`: selector ve `Anime`
  va input custom disabled.

## Luot 4e - Title du an theo goi y duoc chon

Trang thai:
- Title du an sinh don trong History khong lay tu goi y dau tien.
- Backend chi cap nhat title khi user bat dau `Sinh chi tiet`, vi day la luc
  server biet chinh xac suggestion nao duoc chon.
- Project moi van co title nhap tam theo style trong giai doan chi moi sinh goi
  y; sau khi chon goi y va sinh chi tiet, title doi thanh title cua suggestion.

Manual checklist:
- Sinh 5 goi y, chon goi y so khac 1, bam `Sinh chi tiet`.
- Quay ve History: title du an phai bang title cua goi y da chon.
- Legacy series project van bi chan o endpoint sinh don, khong ghi title nham.

## Luot 5 - Chuoi video intake va workbench gon

Trang thai:
- Sidebar `Chuoi video` mo intake trong, khong tu mo series gan nhat.
- Series cu chi mo tu `Lich su` filter `Chuoi video`.
- Da bo rail trai trong `SeriesPage`; breadcrumb `Series > ten series` dua ve
  History filter series.
- Intake co y tuong, title tuy chon, style preset/custom, topic type, so tap,
  scene/tap, giay/scene va model hien tai.
- Timeline chi cho bam tap da sinh/dang sinh va tap tiep theo; tap sau bi
  disabled de tranh nhay continuity.
- Candidate, season slot, continuity, review va phase log nam trong cung workbench,
  khong tach thanh cot history rieng.

Manual checklist:
- Bam sidebar `Chuoi video`: form khoi tao rong.
- Tao series moi: vao workbench tap 1 dung id.
- Mo series tu History: breadcrumb dung va bam `Series` quay lai History series.
- Neu da sinh tap 1 va 2: chi bam duoc 1, 2, 3; tap 4+ disabled.
- Output copy JSON/prompts va tab Continuity/Review/Phase log hoat dong.

## Luot 5a - Series brief truoc output

Trang thai:
- Workbench moi tap tach thanh 2 stage: `Sinh brief` va `Sinh tap & output`.
- Khi bam `Sinh tap nay`, UI luu brief truoc roi chuyen sang output, an toan
  bo form brief/candidate/season slot.
- Output doi tu danh sach scene bung het sang scene navigator compact + panel
  chi tiet scene dang chon.
- Continuity, Review va Phase log nam full-width ben duoi output, khong con
  doc nhu cot rieng.

Manual checklist:
- Tap moi: stage 1 hien brief, bam `Sinh brief` tao candidates.
- Sau khi brief ready: bam `Sinh tap nay` thi stage 1 bien mat.
- Khi output co nhieu scene: chon scene trong navigator doi detail dung.
- Bam `Sua brief` khi khong generating quay lai stage brief.

## Luot 5b - Series output micro polish

Trang thai:
- Header output dung tieu de tap lam noi dung chinh, so scene chuyen thanh
  metadata nho.
- Cot danh sach scene duoc rut ngan va giu scroll rieng de artifact ben duoi
  khong bi day qua xa.
- Preview scene trong navigator duoc cat ngan hon de danh sach doc gon hon.

Manual checklist:
- Output tap da sinh hien tieu de tap thay vi `60 scene`.
- Desktop/mobile: cot scene ngan hon, chon scene va copy prompt van dung.

## Luot 6 - Cai dat va ModelSelector

Trang thai:
- Da polish tab `Cai dat` theo token Cobalt-dark, bo card gradient/tailwind cu
  khoi page nay.
- Layout desktop chia 2 cot: key o cot rong, default/test model o cot phu;
  mobile stack mot cot.
- App key va Gemini key co status card rieng cho `chua luu/dang xac thuc/loi/da luu`.
- `ModelSelector` dung dropdown compact, khong dung emoji lam tin hieu chinh,
  hien quota theo text va progress bar token.

Manual checklist:
- `/settings`: luu/xoa App key, luu/xoa Gemini key van dung.
- Doi model/default language/default duration va bam `Luu mac dinh`.
- Test Gemini khi co key da luu hien success/error dung.
- 320/375/414/768/desktop khong tran ngang, dropdown model khong vuot man.

## Luot 6a - Cai dat bo thoi luong mac dinh

Trang thai:
- Da bo field `Thoi luong mac dinh` khoi tab `Cai dat`.
- Nut `Luu mac dinh` chi luu model va ngon ngu, khong ghi de
  `DEFAULT_DURATION`.

Manual checklist:
- `/settings` khong con field thoi luong.
- Luu mac dinh van luu model/ngon ngu va khong loi TypeScript.

## Luot 7 - Trang thong tin

Trang thai:
- Da polish `Gioi thieu`, `Huong dan su dung`, `Tuyen bo mien tru` theo
  layout token chung `info-*`.
- Da bo noi dung cu ve `chu de hot` va `YouTube URL` trong luong Sinh don.
- Noi dung moi bam vao workflow hien tai: Sinh don manual, Chuoi video
  series.v2, Lich su chung, output scene/prompt.

Manual checklist:
- `/intro`, `/guide`, `/disclaimer` khong tran ngang o 320/375/414/768/desktop.
- Link chinh sach trong disclaimer focus/mouse hover ro va mo tab moi.
- Guide khong con huong dan tinh nang da bo.

## Luot 8 - Sinh don output inline

Trang thai:
- Da nhung output production vao buoc 3 cua tab `Sinh don`; CTA khong day
  sang route `/generate` nua.
- Route `/generate` van duoc giu lam alias tuong thich va render cung
  `SingleOutputPanel`.
- Output doi sang scene navigator + scene detail tabs, khong bung toan bo
  scene dai mot luc.
- Artifact production gom lai thanh tabs: Plan, Prompt 0, Characters,
  Environment, Continuity, Reference.

Manual checklist:
- `/single`: sinh goi y, chon goi y, bam `Sinh kich ban chi tiet` hien output
  inline va stream khong sinh trung.
- Mo project da sinh tu `Lich su` quay ve `Sinh don` buoc output.
- `/generate` cu van hien output va nut quay lai hoat dong.
- Copy scene prompt, all prompts, full script va artifact active deu dung.
- 320/375/414/768/desktop khong tran ngang.

## Luot 5c - Series bo goi y brief

Trang thai:
- Da bo panel `Goi y brief` va danh sach candidate khoi stage brief.
- Nut `Sinh brief` van dung endpoint hien co, nhung tu dong ap dung brief dau
  tien backend tra ve vao form chinh.
- `Vi tri tap` van giu o panel phu ben phai de xem context tap.

Manual checklist:
- Stage brief khong con khung `Goi y brief`.
- Bam `Sinh brief` thi form brief duoc dien/cap nhat truc tiep.
- Sau khi brief ready, `Luu brief` va `Sinh tap nay` van hoat dong.

## Luot 5d - Series copy JSON prompt pack

Trang thai:
- Output series chi con mot nut `Sao chep JSON`.
- JSON copy gom `prompt_0` duoc dung tu series bible, episode blueprint,
  episode brief va danh sach scene prompt/voice.
- Da bo nut copy prompt rieng o header va trong scene detail.

Manual checklist:
- Output series chi hien mot nut sao chep.
- Paste JSON co `schema_version: series.prompt_pack.v1`, `prompt_0`, `scenes`.
- JSON khong co `review_report`, `continuity_delta`, `packaging`, `phase_log`.

## Luot 8a - Video don rename va copy gon

Trang thai:
- Da doi nhan hien thi `Sinh don` thanh `Video don`; route noi bo `/single`
  va code `single` giu nguyen.
- Da bo nut `Sao chep tat ca prompt` trong output Video don.
- Nut `Sao chep toan bo` giu nguyen format ke hoach san xuat, Prompt 0 va
  danh sach scene.

Manual checklist:
- Sidebar, Home, History, Intro, Guide, Single output hien `Video don`.
- Output Video don khong con nut copy tat ca prompt.
- `Sao chep toan bo` van copy du payload mau.

## Luot 9 - Recovery sinh do

Trang thai:
- Da them recovery thu cong cho Video don: project `generating_script` hoac
  `script_failed` mo lai duoc o buoc output, co nut `Tiep tuc sinh` va
  `Sinh lai tu dau`.
- Da them recovery thu cong cho Chuoi video: episode `generating` hoac
  `failed` giu partial artifact, co the resume cache hoac restart output ma
  khong xoa brief.
- Backend khong tu resume khi mo lai de tranh ton quota ngoai y muon; retry
  mac dinh dung artifact hop le da persist, restart bo cache output.

Manual checklist:
- Video don: mo project dang sinh/loi tu Lich su, bam `Tiep tuc sinh`.
- Video don: bam `Sinh lai tu dau`, output cu clear va stream moi.
- Chuoi video: mo episode failed/generating, bam tiep tuc hoac sinh lai.
- Lich su hien label recoverable ro cho project loi/dang sinh.
