# Title and abstract

Two versions below. **Use the proposal-stage abstract now** — it claims a
question and a method, which is all you currently have. The results-stage
version is a template with slots; it must not be submitted until every bracket
holds a real measured number.

---

## Title

### The convention

YSC titles are descriptive three-part constructions, not conference-style
questions. A verified winning title from MWIT shows the shape:

> การประยุกต์ใช้**แบบจำลองการเรียนรู้ของเครื่อง** **เพื่อ**คัดกรองและระบุ
> สารประกอบศักยภาพสูง**สำหรับ**ยับยั้งเอนไซม์โปรติเอส NS2B/NS3 ของไวรัสเดงกี

Structure: **[method] เพื่อ [what it does] สำหรับ/ของ [target domain]**. Method
leads. Length is not a problem — precision is the point. So the title has to
carry all three of: what is studied, how, and what it is for.

### Recommended

**Thai**

> การพัฒนาแบบจำลองเครือข่ายการเคลื่อนย้ายโดยมนุษย์ ร่วมกับการสกัดข้อมูลจาก
> ข้อความภาษาไทยด้วยแบบจำลองภาษาขนาดใหญ่ เพื่อคาดการณ์การแพร่กระจายของ
> ปลาหมอคางดำ และจัดลำดับพื้นที่เฝ้าระวังในระดับตำบล

**English**

> Development of a Human-Transport Network Model Combined with Thai-Language
> Text Mining to Predict the Spread of Blackchin Tilapia (*Sarotherodon
> melanotheron*) and Prioritise Subdistrict-Level Surveillance

Slot by slot:

| Slot | Thai | Carries |
|---|---|---|
| Method 1 | แบบจำลองเครือข่ายการเคลื่อนย้ายโดยมนุษย์ | the novel modelling claim |
| Method 2 | การสกัดข้อมูลจากข้อความภาษาไทยด้วยแบบจำลองภาษาขนาดใหญ่ | the data-creation contribution |
| Studied | การแพร่กระจายของปลาหมอคางดำ | the subject |
| Solves | จัดลำดับพื้นที่เฝ้าระวังในระดับตำบล | the application |

### Shorter, if the form caps the length

> การสกัดข้อมูลจากข้อความภาษาไทยด้วยแบบจำลองภาษาขนาดใหญ่ ร่วมกับแบบจำลอง
> เครือข่ายสองชั้น เพื่อจัดลำดับพื้นที่เฝ้าระวังการแพร่กระจายของปลาหมอคางดำ

Drops "human transport" as an explicit phrase, which costs you the hypothesis in
the title. Prefer the full version if you are allowed the characters.

### Emphasis variants

Lead with whichever contribution you want judged as primary — the title decides
which category you land in and what the judges anchor on.

*If the modelling is the centrepiece* (Environmental Science framing):

> การพัฒนาแบบจำลองเครือข่ายสองชั้นเปรียบเทียบการแพร่กระจายตามแหล่งน้ำกับ
> การเคลื่อนย้ายโดยมนุษย์ เพื่อคาดการณ์การรุกรานของปลาหมอคางดำในประเทศไทย

*If the NLP pipeline is the centrepiece* (Computer Science framing):

> การพัฒนาระบบสกัดข้อมูลการพบชนิดพันธุ์ต่างถิ่นจากข้อความภาษาไทย
> ด้วยแบบจำลองภาษาขนาดใหญ่ เพื่อสร้างฐานข้อมูลการแพร่กระจายของปลาหมอคางดำ

Pick one and stay consistent across the proposal, poster, and abstract.

### Keep the question as a headline, not a title

"ปลาว่ายมาเองหรือคนพามา?" — *Did the fish swim here, or did people bring it?* —
is wrong for the submission form but right for the poster header, the opening
line of your presentation, and the first slide. It states the falsifiable claim
in seven words, which is what you want a judge to remember after walking away.
Use it there; use the descriptive title on the form.

**Short project name** (repo, slide footer): **Kangdam** — what everyone already
calls the fish, and it survives being said out loud in either language.

---

## Proposal-stage abstract — English (~250 words)

> Thailand's blackchin tilapia (*Sarotherodon melanotheron*) invasion has reached
> 19 provinces since 2011. With eradication no longer feasible, national policy
> has shifted to early detection, which requires predicting where the species
> will appear next.
>
> Existing invasion models assume hydrological diffusion: connected water carries
> fish. Published population-genetic work contradicts this for Thailand,
> reporting 19 haplotypes, evidence of multiple independent introductions, and
> regionally distinct populations with limited mixing. Populations that are
> genetically separate were not connected by swimming fish. This project tests
> the alternative — that human movement through aquaculture supply chains, not
> waterway connectivity, governs where the species appears.
>
> Testing that requires more than 19 province-level observations. I therefore
> built a text-mining pipeline that extracts dated, place-named occurrence
> records from Thai-language news, government bulletins, and community posts
> using a language model constrained to a structured schema. Every record carries
> a verbatim source quote and is verified against it; place names are resolved to
> official subdistricts by a deterministic gazetteer rather than by the model.
> The pipeline is validated by independently recovering the documented
> provincial detections and measuring how far in advance it would have flagged
> each one.
>
> The resulting record is fitted to a two-layer network model — waterway
> connectivity against aquaculture-mediated human transport — compared by rolling
> out-of-sample prediction of the next province invaded, against nulls including
> distance-only and aquaculture-area-only. A predictive advantage for the
> human-transport layer, particularly across province pairs that are
> hydrologically disconnected but commercially linked, would support the
> hypothesis. The output is a ranked subdistrict surveillance priority list.

## Proposal-stage abstract — Thai

> ปลาหมอคางดำ (*Sarotherodon melanotheron*) แพร่กระจายในประเทศไทยแล้ว 19 จังหวัด
> นับตั้งแต่ปี พ.ศ. 2554 เมื่อการกำจัดให้หมดสิ้นไม่อาจทำได้อีกต่อไป นโยบายระดับชาติ
> จึงมุ่งไปที่การตรวจพบแต่เนิ่น ซึ่งจำเป็นต้องคาดการณ์ได้ว่าปลาชนิดนี้จะปรากฏที่ใด
> เป็นลำดับถัดไป
>
> แบบจำลองการรุกรานที่ใช้กันอยู่ตั้งอยู่บนสมมติฐานว่าปลาแพร่กระจายไปตามแหล่งน้ำ
> ที่เชื่อมต่อกัน แต่งานวิจัยพันธุศาสตร์ประชากรที่ตีพิมพ์แล้วขัดแย้งกับสมมติฐานนี้
> โดยรายงานแฮโพลไทป์ 19 แบบ หลักฐานการนำเข้าหลายครั้งอย่างเป็นอิสระต่อกัน และประชากร
> ที่แตกต่างกันตามภูมิภาคโดยมีการผสมกันจำกัด ประชากรที่แยกจากกันทางพันธุกรรมย่อมมิได้
> เชื่อมต่อกันด้วยการว่ายน้ำของปลา โครงงานนี้จึงทดสอบสมมติฐานทางเลือกว่า การเคลื่อนย้าย
> โดยมนุษย์ผ่านห่วงโซ่อุปทานการเพาะเลี้ยงสัตว์น้ำ มิใช่ความเชื่อมโยงของแหล่งน้ำ
> เป็นตัวกำหนดการปรากฏของปลาชนิดนี้
>
> การทดสอบดังกล่าวต้องการข้อมูลมากกว่าการตรวจพบระดับจังหวัดเพียง 19 จุด ผู้จัดทำจึง
> พัฒนากระบวนการสกัดข้อมูลจากข้อความภาษาไทย ทั้งข่าว ประกาศของหน่วยงานราชการ และโพสต์
> ในชุมชนออนไลน์ ด้วยแบบจำลองภาษาขนาดใหญ่ที่ถูกกำกับด้วยโครงสร้างข้อมูลที่กำหนดไว้
> ทุกระเบียนต้องมีข้อความอ้างอิงจากต้นฉบับและได้รับการตรวจสอบย้อนกลับ ส่วนชื่อสถานที่
> จะถูกจับคู่กับตำบลตามระบบราชการด้วยวิธีการที่กำหนดตายตัว มิใช่โดยแบบจำลอง การตรวจสอบ
> ความถูกต้องทำโดยให้กระบวนการนี้ค้นพบการตรวจพบระดับจังหวัดที่มีบันทึกอยู่แล้วได้ด้วยตนเอง
> และวัดว่าจะสามารถแจ้งเตือนล่วงหน้าได้นานเพียงใด
>
> ข้อมูลที่ได้จะนำไปปรับกับแบบจำลองเครือข่ายสองชั้น คือความเชื่อมโยงของแหล่งน้ำ เทียบกับ
> การเคลื่อนย้ายโดยมนุษย์ผ่านการเพาะเลี้ยงสัตว์น้ำ โดยเปรียบเทียบด้วยการทำนายจังหวัดถัดไป
> ที่จะถูกรุกรานแบบนอกกลุ่มตัวอย่าง เทียบกับแบบจำลองพื้นฐานที่ใช้เพียงระยะทาง และที่ใช้
> เพียงพื้นที่เพาะเลี้ยงสัตว์น้ำ หากชั้นการเคลื่อนย้ายโดยมนุษย์ทำนายได้ดีกว่า โดยเฉพาะ
> ในคู่จังหวัดที่ไม่เชื่อมต่อกันทางแหล่งน้ำแต่เชื่อมโยงกันทางการค้า ย่อมเป็นหลักฐาน
> สนับสนุนสมมติฐานดังกล่าว ผลลัพธ์คือลำดับความสำคัญของตำบลสำหรับการเฝ้าระวัง

> **Have a Thai teacher read this before submitting.** The technical vocabulary
> is standard but the register may want adjusting to whatever YSC expects, and a
> native reader will catch phrasing a non-native draft will not.

---

## Results-stage abstract — template

Swap this in only when every bracket holds a measured number. Same first two
paragraphs as above; replace from the method paragraph on:

> The pipeline recovered **[N]** of the 19 documented provincial detections from
> text alone, a median **[M]** months before official confirmation, at **[P]%**
> precision on a hand-labelled sample of **[K]** records. It yielded **[R]**
> located occurrence records across **[S]** subdistricts — **[R/19]**× the
> observations available from the official record.
>
> The hybrid model predicted the next province invaded with **[top-3 accuracy]**
> in rolling out-of-sample validation, against **[X]** for waterway connectivity
> alone, **[Y]** for distance only, and **[Z]** for aquaculture area only. The
> human-transport layer's advantage was concentrated in **[D]** province pairs
> that are hydrologically disconnected but commercially linked, consistent with
> the genetic evidence for multiple introductions.
>
> **[T]** subdistricts with no recorded detection ranked above the median
> establishment risk; **[F]** were checked in the field, of which **[G]**
> **[did / did not]** yield confirmed occurrences.

**Rules for filling it in.** State the strict-species-filter number if it differs
from the permissive one — reporting only the more flattering of the two is the
kind of thing a judge finds by asking one follow-up question. If the hybrid model
does *not* beat the waterway model, say so plainly and report it as the finding;
a well-executed negative result against a pre-registered comparison is a
legitimate outcome and defends far better than a hedged positive one.

---

## Keywords

invasive species; *Sarotherodon melanotheron*; blackchin tilapia; human-mediated
dispersal; network model; natural language processing; surveillance
prioritisation; Thailand

ชนิดพันธุ์ต่างถิ่นรุกราน; ปลาหมอคางดำ; การแพร่กระจายโดยมนุษย์; แบบจำลองเครือข่าย;
การประมวลผลภาษาธรรมชาติ; การเฝ้าระวัง

---

## Two things to check against the YSC form

- **Word limit.** The English abstract above is ~250 words. Science-fair forms
  commonly cap at 250; trim the final sentence of the method paragraph first, it
  is the most compressible.
- **First person.** Some forms require impersonal phrasing. If so, replace "I
  therefore built" with "A text-mining pipeline was developed" throughout — but
  keep it consistent, and do not use it to obscure which parts you built
  yourself. Judges specifically ask that.

---

## Source for the title convention

Pattern inferred from a verified YSC winning title from Mahidol Wittayanusorn
School (MWIT): "การประยุกต์ใช้แบบจำลองการเรียนรู้ของเครื่อง เพื่อคัดกรองและระบุ
สารประกอบศักยภาพสูงสำหรับยับยั้งเอนไซม์โปรติเอส NS2B/NS3 ของไวรัสเดงกี"
— https://www.mwit.ac.th/html/news_680211/

Only one title could be retrieved verbatim; NECTEC's project database
(fic.nectec.or.th) and most Thai school sites were unreachable from where this
was drafted. **Check a dozen more titles yourself** in your own category before
finalising — NSTDA publishes finalist lists as PDFs at nstda.or.th/ysc, and the
per-year project database at fic.nectec.or.th is the fuller source. If the
convention in your category differs from the one example above, follow your
category.
