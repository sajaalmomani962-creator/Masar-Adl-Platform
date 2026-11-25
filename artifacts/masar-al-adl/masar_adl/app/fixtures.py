"""Demo seed: a literal copy of db/judicial_exchange_seed_data.sql (same ids, same values).

The seed script has no timestamps for rows that default to SYSDATETIME(); the dates below
are fixed DEMO timestamps chosen to be consistent with the seeded request dates.
"""
from datetime import datetime as D, date

T = D.fromisoformat

SEED = {
    "government_entities": [
        (1, "COURT-AMM-01", "محكمة بداية عمّان", "Amman Court of First Instance", "JUDICIAL", 1),
        (2, "DLS-01", "دائرة الأراضي والمساحة", "Department of Lands and Survey", "GOVERNMENT", 1),
        (3, "CSCD-01", "دائرة الأحوال المدنية والجوازات", "Civil Status and Passports Department", "GOVERNMENT", 1),
        (4, "ISTD-01", "دائرة ضريبة الدخل والمبيعات", "Income and Sales Tax Department", "GOVERNMENT", 1),
        (5, "DVL-01", "إدارة ترخيص السواقين والمركبات", "Driver and Vehicle Licensing Department", "GOVERNMENT", 1),
        (6, "SSC-01", "المؤسسة العامة للضمان الاجتماعي", "Social Security Corporation", "GOVERNMENT", 1),
        (7, "MIT-01", "وزارة الصناعة والتجارة والتموين", "Ministry of Industry, Trade and Supply", "GOVERNMENT", 1),
        (8, "GAM-01", "أمانة عمّان الكبرى", "Greater Amman Municipality", "GOVERNMENT", 1),
    ],
    "users": [
        (1, "TEST-NID-9901001001", "citizen_tariq", "طارق محمود العبدالله", "CITIZEN", "مواطن", None, 1),
        (2, "TEST-NID-9901001002", "citizen_layla", "ليلى حسن النابلسي", "CITIZEN", "مواطن", None, 1),
        (3, "TEST-NID-9902002001", "lawyer_omar", "المحامي عمر خالد الطراونة", "LAWYER", "محامٍ", None, 1),
        (4, "TEST-NID-9902002002", "lawyer_sara", "المحامية سارة أحمد المجالي", "LAWYER", "محامية", None, 1),
        (5, "TEST-NID-9903003001", "clerk_noor", "نور الدين محمد الزعبي", "COURT_CLERK", "كاتب محكمة", 1, 1),
        (6, "TEST-NID-9903003002", "judge_adel", "القاضي عادل إبراهيم الحسن", "COURT_JUDGE", "قاضٍ", 1, 1),
        (7, "TEST-NID-9904004001", "land_officer_rami", "رامي سعيد البطاينة", "LAND_OFFICER", "موظف دائرة الأراضي", 2, 1),
        (8, "TEST-NID-9905005001", "civil_officer_dana", "دانة يوسف الكردي", "CIVIL_STATUS_OFFICER", "موظف الأحوال المدنية", 3, 1),
        (9, "TEST-NID-9906006001", "gov_tax_fadi", "فادي سالم القيسي", "GOV_ENTITY_OFFICER", "موظف جهة حكومية", 4, 1),
        (10, "TEST-NID-9906006002", "gov_gam_hana", "هناء محمود الرواشدة", "GOV_ENTITY_OFFICER", "موظف جهة حكومية", 8, 1),
    ],
    "cases": [
        (1, "2026-CIV-1041", "محكمة بداية حقوق عمّان", "محكمة بداية", "عمّان - العبدلي", "REAL_ESTATE", "عقارية",
         2026, "BIDAYAH", "بداية", date(2026, 2, 10), "WAITING_FOR_DOCUMENTS", "بانتظار وثائق من الجهات", 1, 3,
         "دعوى إثبات ملكية وحقوق ارتفاق لقطعة أرض في عمّان.", "بحث بالرقم الوطني / اسم الطرف"),
        (2, "2026-CIV-2088", "محكمة صلح حقوق عمّان", "محكمة صلح", "عمّان - وسط البلد", "CIVIL", "حقوقية مدنية",
         2026, "SULH", "صلح", date(2026, 4, 5), "IN_PROGRESS", "قيد المتابعة والإجراءات", 2, 4,
         "مطالبة مالية وتدقيق بيانات سجل وعنوان طرف الدعوى.", "بحث باسم الطرف / المؤسسة"),
    ],
    "case_parties": [
        (1, 1, 1, "CLAIMANT", "مدّعٍ", 1, "طارق محمود العبدالله", "TEST-NID-9901001001", None, "PERSON", "شخص طبيعي"),
        (2, 1, 3, "AUTHORIZED_LAWYER", "وكيل بالخصومة", 0, "المحامي عمر خالد الطراونة", "TEST-NID-9902002001", None, "PERSON", "شخص طبيعي"),
        (3, 1, None, "DEFENDANT", "مدّعى عليه", 0, "شركة البناء الحديث للتطوير", "TEST-INST-501", "شركة البناء الحديث للتطوير", "INSTITUTION", "مؤسسة / شركة"),
        (4, 2, 2, "CLAIMANT", "مدّعية", 1, "ليلى حسن النابلسي", "TEST-NID-9901001002", None, "PERSON", "شخص طبيعي"),
        (5, 2, 4, "AUTHORIZED_LAWYER", "وكيلة بالخصومة", 0, "المحامية سارة أحمد المجالي", "TEST-NID-9902002002", None, "PERSON", "شخص طبيعي"),
    ],
    # request_id, case_id, requested_by, target_entity, type, title, status, submitted_at(demo),
    # decision_by, decision_at, sent_at, response_at, delay_days, delay_code, public_msg, internal_note
    "document_requests": [
        (1, 1, 3, 2, "LAND_OWNERSHIP_EXTRACT", "طلب مخطط أراضي ومستند ملكية لقطعة رقم 45", "RESPONSE_RECEIVED",
         T("2026-03-01 09:00:00"), 6, T("2026-03-02 10:30:00"), T("2026-03-03 08:15:00"), T("2026-03-12 13:45:00"),
         0, None, "تم استلام رد دائرة الأراضي وإرفاقه بملف الدعوى.", "الرد مطابق للبيانات المساحية المرفقة."),
        (2, 1, 3, 8, "ZONING_STATUS_LETTER", "طلب بيان تنظيم وموافقة بلدية لموقع العقار", "DELAYED",
         T("2026-05-09 09:00:00"), 6, T("2026-05-10 11:00:00"), T("2026-05-11 09:00:00"), None,
         6, "ENTITY_QUEUE_BACKLOG", "الكتاب مرسل إلى أمانة عمّان الكبرى وقيد المعالجة مع تأخير إداري.", "تم إرسال تنبيه متابعة للجهة."),
        (3, 2, 4, 3, "CIVIL_RECORD_CHECK", "طلب قيد فردي ومطابقة بيانات هوية", "APPROVED",
         T("2026-06-14 09:00:00"), 6, T("2026-06-15 09:40:00"), None, None,
         0, None, "تمت موافقة المحكمة على الكتاب وجارٍ إرساله للأحوال المدنية.", "جاهز للإرسال الإلكتروني."),
    ],
    "documents": [
        (1, 1, "LAWYER_REQUEST_PDF", "نسخة PDF لطلب المحامي", "طلب كتاب دائرة الأراضي - نسخة مقدم الطلب",
         "req_1041_dls_request_test.pdf", 3, "COURT_AND_AUTHORIZED_LAWYER", "المحكمة والمحامي الموكل فقط", 0, 0,
         "UPLOADED", "مرفوع", "غير متاح للطباعة للمواطن", "مرفق رقمي تجريبي أولي", "معاينة", T("2026-03-01 09:05:00")),
        (2, 1, "ENTITY_RESPONSE", "رد الجهة الحكومية", "مخطط أراضي ومستند ملكية صادر عن دائرة الأراضي",
         "resp_1041_dls_extract_test.pdf", 7, "CITIZEN_AND_LAWYER", "المواطن والمحامي الموكل", 1, 1,
         "RECEIVED", "مستلم", "متاح للطباعة للمواطن والمحامي", "وثيقة تجريبية تمثل رد الجهة المختصة", "تنزيل وطباعة", T("2026-03-12 13:45:00")),
        (3, 2, "PUBLIC_STATUS_CERTIFICATE", "شهادة حالة عامة", "إشعار متابعة طلب بيان التنظيم",
         "status_1041_gam_notice_test.pdf", 5, "CITIZEN_AND_LAWYER", "المواطن والمحامي الموكل", 1, 0,
         "AVAILABLE", "متاح", "متاح للطباعة للمواطن", "إشعار حالة تجريبي يوضح تأخر الرد", "عرض الحالة", T("2026-05-20 10:00:00")),
    ],
    "request_timeline": [
        (1, 1, "REQUEST_SUBMITTED", "قدّم المحامي طلب كتاب إلى دائرة الأراضي والمساحة.", 3, T("2026-03-01 09:10:00"), 1),
        (2, 1, "COURT_APPROVED", "وافق القاضي على إرسال الكتاب إلى دائرة الأراضي.", 6, T("2026-03-02 10:30:00"), 1),
        (3, 1, "ENTITY_RESPONSE_RECEIVED", "وردت إجابة دائرة الأراضي وتمت إتاحتها في ملف الطلب.", 7, T("2026-03-12 13:45:00"), 1),
        (4, 2, "REQUEST_DELAYED", "تجاوز الطلب المدة المعتادة لدى الجهة وتم تسجيل تأخير 6 أيام.", 10, T("2026-05-20 10:00:00"), 1),
    ],
    "audit_logs": [
        (1, 3, 1, 1, "CREATE_DOCUMENT_REQUEST", T("2026-03-01 09:00:00"), "SUCCESS", "إنشاء طلب كتاب جديد موجه لدائرة الأراضي على القضية 2026-CIV-1041."),
        (2, 6, 1, 1, "APPROVE_DOCUMENT_REQUEST", T("2026-03-02 10:30:00"), "SUCCESS", "اعتماد طلب الكتاب رقم 1 من قبل القاضي."),
        (3, 7, 1, 1, "UPLOAD_ENTITY_RESPONSE", T("2026-03-12 13:45:00"), "SUCCESS", "رفع رد دائرة الأراضي على الطلب رقم 1."),
        (4, 1, 2, None, "VIEW_CASE_SUMMARY", T("2026-04-06 11:00:00"), "SUCCESS", "استعلام المواطن عن ملخص القضية 2026-CIV-2088."),
    ],
    "notifications": [
        (1, 1, 1, "RESPONSE_AVAILABLE", "وصول رد جهة", "تم استلام رد دائرة الأراضي على طلب الكتاب الخاص بقضيتك رقم 2026-CIV-1041.", T("2026-03-12 13:46:00"), 0),
        (2, 3, 2, "REQUEST_DELAYED", "تنبيه تأخير طلب", "سُجل تأخير 6 أيام على طلب بيان التنظيم المرسل إلى أمانة عمّان الكبرى.", T("2026-05-20 10:01:00"), 0),
        (3, 4, 3, "REQUEST_APPROVED", "اعتماد طلب كتاب", "تمت موافقة المحكمة على طلب القيد الفردي للقضية رقم 2026-CIV-2088.", T("2026-06-15 09:41:00"), 1),
    ],
    "document_permissions": [
        (1, "CITIZEN", "LAWYER_REQUEST_PDF", 0, 0, 0),
        (2, "CITIZEN", "ENTITY_RESPONSE", 1, 1, 1),
        (3, "CITIZEN", "PUBLIC_STATUS_CERTIFICATE", 1, 1, 1),
        (4, "LAWYER", "LAWYER_REQUEST_PDF", 1, 1, 1),
        (5, "LAWYER", "ENTITY_RESPONSE", 1, 1, 1),
        (6, "LAWYER", "PUBLIC_STATUS_CERTIFICATE", 1, 1, 1),
        (7, "COURT_CLERK", "LAWYER_REQUEST_PDF", 1, 1, 0),
        (8, "COURT_CLERK", "ENTITY_RESPONSE", 1, 1, 0),
        (9, "COURT_CLERK", "PUBLIC_STATUS_CERTIFICATE", 1, 1, 1),
        (10, "COURT_JUDGE", "LAWYER_REQUEST_PDF", 1, 1, 0),
        (11, "COURT_JUDGE", "ENTITY_RESPONSE", 1, 1, 0),
        (12, "COURT_JUDGE", "PUBLIC_STATUS_CERTIFICATE", 1, 0, 0),
        (13, "LAND_OFFICER", "ENTITY_RESPONSE", 1, 1, 0),
        (14, "CIVIL_STATUS_OFFICER", "ENTITY_RESPONSE", 1, 1, 0),
        (15, "GOV_ENTITY_OFFICER", "ENTITY_RESPONSE", 1, 1, 0),
    ],
}

# column order of the tuples above (pk first)
COLUMNS = {
    "government_entities": ["entity_id", "entity_code", "entity_name_ar", "entity_name_en", "entity_type", "is_active"],
    "users": ["user_id", "national_id", "username", "display_name", "role", "role_ar", "entity_id", "is_active"],
    "cases": ["case_id", "case_number", "court_name", "court_type_ar", "court_location_ar", "case_type", "case_type_ar",
              "case_year", "registry_type", "registry_type_ar", "opened_date", "case_status", "case_status_ar",
              "citizen_user_id", "lawyer_user_id", "public_summary_ar", "party_search_type_ar"],
    "case_parties": ["case_party_id", "case_id", "user_id", "party_role", "party_role_ar", "is_primary", "party_name_ar",
                     "party_identifier", "institution_name_ar", "party_category", "party_category_ar"],
    "document_requests": ["request_id", "case_id", "requested_by_user_id", "target_entity_id", "request_type",
                          "request_title_ar", "request_status", "submitted_at", "court_decision_by_user_id",
                          "court_decision_at", "sent_to_entity_at", "response_received_at", "delay_days",
                          "delay_reason_code", "public_status_message_ar", "internal_note"],
    "documents": ["document_id", "request_id", "document_type", "document_type_ar", "document_title_ar", "file_name",
                  "uploaded_by_user_id", "visibility", "visibility_ar", "is_printable_by_citizen", "is_official",
                  "document_status", "document_status_ar", "print_permission_note_ar", "attachment_notes_ar",
                  "attachment_action_ar", "uploaded_at"],
    "request_timeline": ["timeline_id", "request_id", "event_code", "event_description_ar", "actor_user_id", "event_at",
                         "is_visible_to_citizen"],
    "audit_logs": ["audit_id", "actor_user_id", "case_id", "request_id", "action_code", "action_at", "result", "details"],
    "notifications": ["notification_id", "user_id", "request_id", "notification_type", "notification_type_ar",
                      "message_ar", "created_at", "is_read"],
    "document_permissions": ["permission_id", "role", "document_type", "can_view", "can_download", "can_print"],
}


def load_seed():
    """Return {table: [row dict, ...]} built from SEED."""
    out = {}
    for table, rows in SEED.items():
        cols = COLUMNS[table]
        out[table] = [dict(zip(cols, r)) for r in rows]
    return out


EXPECTED_COUNTS = {t: len(r) for t, r in SEED.items()}
