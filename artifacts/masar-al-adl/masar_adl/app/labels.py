STATUS_AR = {
    "DRAFT": "مسودة", "SUBMITTED": "مقدَّم", "UNDER_COURT_REVIEW": "قيد مراجعة المحكمة",
    "APPROVED": "معتمد", "REJECTED": "مرفوض", "SENT_TO_ENTITY": "أُرسل للجهة",
    "UNDER_PROCESSING": "قيد المعالجة", "DELAYED": "متأخر", "RESPONSE_RECEIVED": "تم استلام الرد",
    "RETURNED_FOR_MODIFICATION": "معاد للتعديل",
}
STATUS_CLASS = {
    "DRAFT": "secondary", "SUBMITTED": "info", "UNDER_COURT_REVIEW": "primary", "APPROVED": "success",
    "REJECTED": "danger", "SENT_TO_ENTITY": "info", "UNDER_PROCESSING": "primary", "DELAYED": "warning",
    "RESPONSE_RECEIVED": "success", "RETURNED_FOR_MODIFICATION": "warning",
}
DELAY_REASONS = {
    "ENTITY_QUEUE_BACKLOG": "ازدحام في قائمة الانتظار لدى الجهة",
    "MISSING_INFORMATION": "نقص في المعلومات المطلوبة",
    "SYSTEM_UNAVAILABLE": "عطل أو توقف في نظام الجهة",
    "OTHER": "سبب آخر",
}
DOC_TYPE_AR = {
    "LAWYER_REQUEST_PDF": "نسخة PDF لطلب المحامي",
    "ENTITY_RESPONSE": "رد الجهة الحكومية",
    "PUBLIC_STATUS_CERTIFICATE": "شهادة حالة عامة",
}
# request types per target entity (application config, not DB): seed types first.
ENTITY_REQUEST_TYPES = {
    2: [("LAND_OWNERSHIP_EXTRACT", "مخطط أراضي ومستند ملكية")],
    3: [("CIVIL_RECORD_CHECK", "قيد فردي ومطابقة بيانات هوية")],
    8: [("ZONING_STATUS_LETTER", "بيان تنظيم وموافقة بلدية")],
}
GENERIC_TYPE = ("GENERAL_OFFICIAL_LETTER", "كتاب رسمي عام")
EVENT_AR = {
    "REQUEST_CREATED": "إنشاء مسودة", "REQUEST_SUBMITTED": "تقديم الطلب",
    "REVIEW_STARTED": "بدء مراجعة المحكمة", "RETURNED_FOR_MODIFICATION": "إعادة للتعديل",
    "COURT_APPROVED": "موافقة القاضي", "COURT_REJECTED": "رفض القاضي", "SENT_TO_ENTITY": "إرسال للجهة",
    "PROCESSING_STARTED": "بدء المعالجة", "REQUEST_DELAYED": "تسجيل تأخير", "PROCESSING_RESUMED": "استئناف المعالجة",
    "RESPONSE_RECEIVED": "وصول رد الجهة", "ENTITY_RESPONSE_RECEIVED": "وصول رد الجهة",
    "RESPONSE_RELEASED": "إتاحة الرد للمواطن", "INTERNAL_NOTE": "ملاحظة داخلية",
}
ROLE_HOME = {
    "CITIZEN": "/citizen", "LAWYER": "/lawyer", "COURT_CLERK": "/court", "COURT_JUDGE": "/court",
    "LAND_OFFICER": "/entity", "CIVIL_STATUS_OFFICER": "/entity", "GOV_ENTITY_OFFICER": "/entity",
}
COURT_ROLES = {"COURT_CLERK", "COURT_JUDGE"}
ENTITY_ROLES = {"LAND_OFFICER", "CIVIL_STATUS_OFFICER", "GOV_ENTITY_OFFICER"}
