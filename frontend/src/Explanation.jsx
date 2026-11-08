import { useEffect, useRef } from "react";
import { convertToExcalidrawElements, exportToSvg } from "@excalidraw/excalidraw";
import { handoffScene, rubricScene, stackScene } from "./scenes";

const copy = {
  en: {
    title: "Explanation",
    lede: "How a review runs, which part of the assignment it answers, and which tool does the work.",
    flowTitle: "How a review runs",
    flowBody: "A person loads a synthetic batch for one tenant. The orchestrator splits it. The extractor writes fields and keeps the page reference. The classifier proposes a VAT treatment and a labelled corporate-tax note. The researcher may attach only a passage from the frozen FTA and MoF register, with its version. The validator is Python: schema, required fields, and arithmetic. It can send an invoice back once. A missing buyer identifier stays to verify, because the repair cannot invent one. The auditor samples the call without the classifier’s reasoning. A disagreement is escalated. The person approves, rejects, or escalates. The signed result is a readiness note on this desk.",
    flowCaption: "Lavender nodes call a model. The green validator does not. A sand box is a stop: one repair, then the row is held, or the auditor disagrees. The approver sees both.",
    flowLabel: "Excalidraw diagram of the review handoff, from the synthetic batch to the bounded pack.",
    stackTitle: "Where the work sits",
    stackBody: "The desk is React and Vite, served by nginx on port 8420. The API is FastAPI on port 8421. Each node emits a server-sent event, so the trace on screen is the run. SQLite on a tenant volume stores the document hash, source version, model, checker outcome, and the person who signed. A second volume holds backups. Every model call is one chat completion to the local OmniRoute gateway on port 20128. The primary model is gh/gpt-5.6-terra. One retry uses gh/gpt-5.6-luna. This repo does not start that gateway and does not change it. If the gateway is down, the desk plays a labelled replay and says those timings are not live measurements.",
    stackGate: "RESIDENCY_VERIFIED defaults to false. A localhost address does not prove where an upstream provider processes data. While the flag is false, only synthetic content is sent. Any other upload is refused before a model call.",
    stackCaption: "The gate sits in front of the graph. A synthetic run may call OmniRoute. Anything else stops. The audit row is written to the tenant volume and copied to the backup volume.",
    stackLabel: "Excalidraw diagram of the desk, the API, the residency gate, LangGraph, OmniRoute, and the two volumes.",
    askTitle: "How this answers the assignment",
    askBody: "The brief asks for a functioning code-first agent, a complete frontend and backend, and a 15-minute presentation: the problem, the architecture and tools, a live demo, the challenges, and a DataRobot vision.",
    askLabel: "Excalidraw diagram of the four assignment criteria: problem, technical credibility, creativity, and strategic vision.",
    problemTitle: "Problem",
    problemBody: "UAE finance teams cannot treat a PDF as an eInvoice. The required invoice is structured data. The original July 2026 appointment date moved, and the FTA notice of 25 October 2026 schedules the larger cohort at AED 50 million and above. One model checking its own batch would hide a bad total or a stale deadline. The work is split so each role owns one of those risks. Research date 2026-11-07. The tenant on the desk is Desert Ledger Trading, and the registration number is labelled synthetic.",
    techTitle: "Technical credibility",
    techBody: "Each role is a LangGraph node with its own prompt and a Pydantic output schema. The validator is ordinary code. Repair stops after one attempt. The auditor does not receive the classifier’s reasoning. A cross-tenant read is refused before lookup. Approval waits until the checker has finished and the document hash is unchanged. The supported start is docker compose up. A reviewer does not install Python or Node on the host.",
    createTitle: "Creativity",
    createBody: "Invoice DL-INV-1002 is missing a buyer identifier and its totals do not meet. The classifier still proposes a treatment. The validator names the failed rule, uses the one repair, and holds the row. The auditor disagrees on the free-zone invoice and on the conflicting revenue invoice. An older deadline loses to the newer FTA source. Asking in Arabic why AED 375,000 does not set the eInvoicing phase returns a desk translation with the English passage beside it. That figure is a corporate-tax band.",
    visionTitle: "Strategic vision",
    visionBody: "A customer would keep this agent core and swap a versioned jurisdiction pack, then run it in containers with storage, logs, backups, and inference pointed at a location that has been checked. The build shows that gate. It leaves OmniRoute unverified. No savings figure is claimed, and nothing is sent to an accredited provider.",
    demoTitle: "What the six demo minutes show",
    demoBody: "The tenant and its stated revenue, the batch splitting on the trace, the seeded rejection, the Arabic threshold question with the English citation, the auditor’s disagreement, and a bounded signature. A refusal is part of the same path. Challenges a speaker can say are the ones written after the build: the AED 50 million sources disagree on “equal”, the repair cannot invent a buyer, and the 90 percent accountant target is not a result.",
    toolsTitle: "Tools used to deliver it",
    toolsCaption: "The same path as the runtime diagram, with the reason each tool is in the repo.",
    tools: [
      ["LangGraph", "Runs the seven roles as nodes in one process.", "The handoff is the product. No graph database is called."],
      ["Pydantic", "Schema for each node’s output.", "The next node receives fields, not a free paragraph."],
      ["Python validator", "Buyer identifier, totals, duplicate id, stale deadline, and the AED 50 million boundary.", "A second model is not the proof."],
      ["FastAPI", "Documents, runs, server-sent events, decisions, reports, and questions.", "The desk and the graph share one contract."],
      ["React and Vite", "Companies, statistics, the review, and this page.", "The reviewer watches the trace, asks, and signs."],
      ["SQLite", "Tenant, document hash, source version, model, checker, and approver.", "The audit row stays on the volume after a restart."],
      ["Docker Compose", "A frontend container, an API container, and two volumes.", "The start command is docker compose up."],
      ["OmniRoute", "OpenAI-compatible chat completions on port 20128.", "One local gateway. This repo does not call a provider SDK."],
      ["pytest", "Arithmetic, abstention, cross-tenant reads, thresholds, the stale deadline, and the residency refusal.", "The demo claims are tied to an answer key."],
      ["Gitleaks, TruffleHog, Trivy, Semgrep", "Scan this repo from the security profile.", "Secret verification stays off."],
    ],
  },
  ar: {
    title: "الشرح",
    lede: "كيف تجري المراجعة، وأي بند من المطلوب تجيبه، وأي أداة تؤدي العمل.",
    flowTitle: "كيف تجري المراجعة",
    flowBody: "يحمّل شخص دفعة تجريبية لمستأجر واحد. يقسمها المنسق. يكتب المستخرج الحقول ويبقي مرجع الصفحة. يقترح المصنف معالجة ضريبة القيمة المضافة وملاحظة تعليمية عن ضريبة الشركات. لا يرفق الباحث إلا مقطعاً من سجل الهيئة ووزارة المالية المجمّد، مع إصداره. المدقق كود بايثون: المخطط، والحقول المطلوبة، والحساب. يمكنه إعادة الفاتورة مرة واحدة. يبقى معرّف المشتري الناقص للمراجعة، لأن الإصلاح لا يخترع معرّفاً. يأخذ المدقق المستقل عينة من النداء دون تعليل المصنف. الاختلاف يُصعَّد. يوافق الشخص أو يرفض أو يصعّد. النتيجة الموقّعة ملاحظة جاهزية على هذا المكتب.",
    flowCaption: "العقد البنفسجية تستدعي نموذجاً. المدقق الأخضر لا يستدعي نموذجاً. العقد الرملية توقف: إصلاح واحد ثم يُحبس الصف، أو يختلف المدقق المستقل. المعتمد يرى الحالتين.",
    flowLabel: "رسم إكسكاليدرو لتسليم المراجعة، من الدفعة التجريبية إلى الحزمة المحدودة.",
    stackTitle: "أين يجلس العمل",
    stackBody: "المكتب ريأكت وفايت، يقدّمه إنجن إكس على المنفذ 8420. الواجهة فاست إي بي آي على المنفذ 8421. كل عقدة ترسل حدثاً، فالأثر على الشاشة هو التشغيل نفسه. تخزّن سكولايت على حجم المستأجر بصمة المستند وإصدار المصدر والنموذج ونتيجة المدقق والشخص الموقّع. حجم ثانٍ يحمل النسخ الاحتياطية. كل نداء نموذج هو إكمال محادثة واحد إلى بوابة أومني روت المحلية على المنفذ 20128. النموذج الأساسي gh/gpt-5.6-terra. إعادة المحاولة الوحيدة تستخدم gh/gpt-5.6-luna. هذا المستودع لا يشغّل تلك البوابة ولا يغيّرها. إذا كانت البوابة متوقفة، يعرض المكتب إعادة موسومة ويقول إن تلك الأزمنة ليست قياسات حية.",
    stackGate: "قيمة RESIDENCY_VERIFIED الافتراضية خطأ. عنوان الجهاز المحلي لا يثبت أين يعالج مزود أعلى البيانات. ما دام العلم مغلقاً، لا يُرسل إلا المحتوى التجريبي. أي رفع آخر يُرفض قبل نداء النموذج.",
    stackCaption: "البوابة أمام الرسم. التشغيل التجريبي قد ينادي أومني روت. أي شيء آخر يتوقف. يُكتب صف التدقيق في حجم المستأجر ويُنسخ إلى حجم النسخ الاحتياطية.",
    stackLabel: "رسم إكسكاليدرو للمكتب والواجهة وبوابة الإقامة ولانغ غراف وأومني روت والحجمين.",
    askTitle: "كيف يجيب هذا المطلوب",
    askBody: "يطلب التكليف وكيلاً يعمل بالكود أولاً، وتطبيقاً كاملاً بواجهة وخلفية، وعرضاً من خمس عشرة دقيقة: المسألة، والبنية والأدوات، وعرضاً حياً، والتحديات، ورؤية داتاروبوت.",
    askLabel: "رسم إكسكاليدرو لمعايير التكليف الأربعة: المسألة، والمصداقية التقنية، والإبداع، والرؤية.",
    problemTitle: "المسألة",
    problemBody: "لا تستطيع فرق المالية في الإمارات معاملة ملف بي دي إف كفاتورة إلكترونية. الفاتورة المطلوبة بيانات منظمة. انتقل موعد التعيين الأصلي في يوليو 2026، وإشعار الهيئة في 25 أكتوبر 2026 يجدول الشريحة الأكبر عند 50 مليون درهم فأكثر. نموذج واحد يراجع دفعته بنفسه يخفي مجموعاً خاطئاً أو موعداً قديماً. ينقسم العمل حتى يملك كل دور أحد هذه المخاطر. تاريخ البحث 2026-11-07. المستأجر على المكتب ديزرت ليدجر للتجارة، ورقم التسجيل موسوم تجريبي.",
    techTitle: "المصداقية التقنية",
    techBody: "كل دور عقدة لانغ غراف لها موجّهها ومخطط بيدانتيك لمخرجاتها. المدقق كود عادي. يتوقف الإصلاح بعد محاولة واحدة. لا يصل المدقق المستقل إلى تعليل المصنف. تُرفض قراءة مستأجر آخر قبل البحث. ينتظر الاعتماد انتهاء المدقق وبقاء بصمة المستند كما هي. أمر البدء هو docker compose up. المراجع لا يثبّت بايثون ولا نود على جهازه.",
    createTitle: "الإبداع",
    createBody: "الفاتورة DL-INV-1002 بلا معرّف مشتري ومجاميعها لا تتطابق. المصنف يقترح معالجة رغم ذلك. يسمّي المدقق القاعدة المخالفة، ويستخدم الإصلاح الوحيد، ويبقي الصف. يختلف المدقق المستقل على فاتورة المنطقة الحرة وعلى فاتورة الإيراد المتعارض. يخسر الموعد الأقدم لصالح مصدر الهيئة الأحدث. السؤال بالعربية عن سبب أن 375000 درهم لا يحدد مرحلة الفوترة الإلكترونية يعيد ترجمة المكتب مع المقطع الإنجليزي بجانبها. ذلك الرقم شريحة لضريبة الشركات.",
    visionTitle: "الرؤية",
    visionBody: "يبقي العميل نواة الوكيل ويستبدل حزمة اختصاص بإصدار، ثم يشغّلها في حاويات مع تخزين وسجلات ونسخ احتياطية واستدلال في موقع تم التحقق منه. البناء يُظهر هذه البوابة. يترك أومني روت غير متحقق. لا يُدّعى رقم توفير، ولا يُرسل شيء إلى مزود معتمد.",
    demoTitle: "ما تظهره دقائق العرض الست",
    demoBody: "المستأجر وإيراده المصرّح به، وانقسام الدفعة على الأثر، والرفض المزروع، وسؤال العتبة بالعربية مع الاستشهاد الإنجليزي، واختلاف المدقق المستقل، ثم توقيع محدود. الرفض جزء من المسار نفسه. التحديات التي يمكن قولها هي المكتوبة بعد البناء: مصدران يختلفان عند «المساوي» لخمسين مليون درهم، والإصلاح لا يخترع مشترياً، وهدف التسعين بالمئة من المحاسب ليس نتيجة.",
    toolsTitle: "الأدوات التي سلّمت العمل",
    toolsCaption: "المسار نفسه في رسم التشغيل، مع سبب وجود كل أداة في المستودع.",
    tools: [
      ["LangGraph", "يشغّل الأدوار السبعة كعقد في عملية واحدة.", "التسليم هو المنتج. لا تُستدعى قاعدة بيانات رسوم."],
      ["Pydantic", "مخطط لمخرجات كل عقدة.", "العقدة التالية تستلم حقولاً، لا فقرة حرة."],
      ["مدقق بايثون", "معرّف المشتري، والمجاميع، والمعرّف المكرر، والموعد القديم، وحد خمسين مليون درهم.", "نموذج ثانٍ ليس هو البرهان."],
      ["FastAPI", "المستندات، والتشغيل، والأحداث، والقرارات، والتقارير، والأسئلة.", "المكتب والرسم يشتركان في عقد واحد."],
      ["React و Vite", "الشركات، والإحصاءات، والمراجعة، وهذه الصفحة.", "المراجع يشاهد الأثر ويسأل ويوقّع."],
      ["SQLite", "المستأجر، وبصمة المستند، وإصدار المصدر، والنموذج، والمدقق، والمعتمد.", "يبقى صف التدقيق على الحجم بعد إعادة التشغيل."],
      ["Docker Compose", "حاوية واجهة، وحاوية واجهة برمجية، وحجمان.", "أمر البدء هو docker compose up."],
      ["OmniRoute", "إكمال محادثة متوافق مع أوبن إي آي على المنفذ 20128.", "بوابة محلية واحدة. هذا المستودع لا يستدعي حزمة مزود."],
      ["pytest", "الحساب، والامتناع، وقراءة المستأجر الآخر، والعتبات، والموعد القديم، ورفض الإقامة.", "ادعاءات العرض مربوطة بمفتاح إجابة."],
      ["Gitleaks و TruffleHog و Trivy و Semgrep", "تفحص هذا المستودع من ملف الأمان.", "التحقق من الأسرار يبقى مغلقاً."],
    ],
  },
};

function Sketch({ skeleton, label }) {
  const host = useRef(null);

  useEffect(() => {
    const node = host.current;
    if (!node) return undefined;
    let cancelled = false;
    const elements = convertToExcalidrawElements(skeleton, { regenerateIds: false });
    exportToSvg({
      elements,
      appState: {
        exportBackground: true,
        viewBackgroundColor: "#f4f3fb",
      },
      files: null,
      exportPadding: 24,
    }).then((svg) => {
      if (cancelled) return;
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", label);
      svg.style.width = "100%";
      svg.style.height = "auto";
      svg.style.display = "block";
      node.replaceChildren(svg);
    }).catch(() => {
      if (!cancelled) node.replaceChildren();
    });
    return () => {
      cancelled = true;
    };
  }, [skeleton, label]);

  return <div className="sketch" ref={host} />;
}

export default function Explanation({ lang }) {
  const t = copy[lang] || copy.en;
  const heading = useRef(null);

  useEffect(() => {
    heading.current?.focus();
  }, [lang]);

  return (
    <article className="explain">
      <h1 ref={heading} tabIndex={-1}>{t.title}</h1>
      <p className="lede">{t.lede}</p>

      <h2>{t.flowTitle}</h2>
      <p>{t.flowBody}</p>
      <figure className="sketch-frame" dir="ltr">
        <Sketch skeleton={handoffScene} label={t.flowLabel} />
        <figcaption>{t.flowCaption}</figcaption>
      </figure>

      <h2>{t.stackTitle}</h2>
      <p>{t.stackBody}</p>
      <p>{t.stackGate}</p>
      <figure className="sketch-frame" dir="ltr">
        <Sketch skeleton={stackScene} label={t.stackLabel} />
        <figcaption>{t.stackCaption}</figcaption>
      </figure>

      <h2>{t.askTitle}</h2>
      <p>{t.askBody}</p>
      <figure className="sketch-frame" dir="ltr">
        <Sketch skeleton={rubricScene} label={t.askLabel} />
      </figure>
      <h3>{t.problemTitle}</h3>
      <p>{t.problemBody}</p>
      <h3>{t.techTitle}</h3>
      <p>{t.techBody}</p>
      <h3>{t.createTitle}</h3>
      <p>{t.createBody}</p>
      <h3>{t.visionTitle}</h3>
      <p>{t.visionBody}</p>
      <h3>{t.demoTitle}</h3>
      <p>{t.demoBody}</p>

      <h2>{t.toolsTitle}</h2>
      <p>{t.toolsCaption}</p>
      <ul className="tool-list">
        {t.tools.map(([name, job, why]) => (
          <li key={name}>
            <span className="ltr">{name}</span>
            <p>{job} {why}</p>
          </li>
        ))}
      </ul>
    </article>
  );
}
