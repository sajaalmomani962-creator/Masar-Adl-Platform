-- ============================================================================
-- بيانات تجريبية وهمية مترابطة لمنصة تبادل الكتب القضائية - SQL Server (T-SQL)
-- متوافقة مع قاعدة البيانات JudicialExchangeDB (الجداول الـ 10)
-- الأرقام الوطنية واسم المستخدم وهمية بالكامل ولا تعتمد على بريد إلكتروني
-- ============================================================================

USE JudicialExchangeDB;
GO

-- 1. إدخال الجهات الحكومية والقضائية (government_entities)
INSERT INTO government_entities (entity_code, entity_name_ar, entity_name_en, entity_type, is_active)
VALUES
(N'COURT-AMM-01', N'محكمة بداية عمّان', N'Amman Court of First Instance', N'JUDICIAL', 1),
(N'DLS-01', N'دائرة الأراضي والمساحة', N'Department of Lands and Survey', N'GOVERNMENT', 1),
(N'CSCD-01', N'دائرة الأحوال المدنية والجوازات', N'Civil Status and Passports Department', N'GOVERNMENT', 1),
(N'ISTD-01', N'دائرة ضريبة الدخل والمبيعات', N'Income and Sales Tax Department', N'GOVERNMENT', 1),
(N'DVL-01', N'إدارة ترخيص السواقين والمركبات', N'Driver and Vehicle Licensing Department', N'GOVERNMENT', 1),
(N'SSC-01', N'المؤسسة العامة للضمان الاجتماعي', N'Social Security Corporation', N'GOVERNMENT', 1),
(N'MIT-01', N'وزارة الصناعة والتجارة والتموين', N'Ministry of Industry, Trade and Supply', N'GOVERNMENT', 1),
(N'GAM-01', N'أمانة عمّان الكبرى', N'Greater Amman Municipality', N'GOVERNMENT', 1);
GO

-- 2. إدخال المستخدمين (users) - أرقام وطنية وهمية + اسم مستخدم بدون بريد إلكتروني
INSERT INTO users (national_id, username, display_name, role, role_ar, entity_id, is_active)
VALUES
(N'TEST-NID-9901001001', N'citizen_tariq', N'طارق محمود العبدالله', N'CITIZEN', N'مواطن', NULL, 1),
(N'TEST-NID-9901001002', N'citizen_layla', N'ليلى حسن النابلسي', N'CITIZEN', N'مواطن', NULL, 1),
(N'TEST-NID-9902002001', N'lawyer_omar', N'المحامي عمر خالد الطراونة', N'LAWYER', N'محامٍ', NULL, 1),
(N'TEST-NID-9902002002', N'lawyer_sara', N'المحامية سارة أحمد المجالي', N'LAWYER', N'محامية', NULL, 1),
(N'TEST-NID-9903003001', N'clerk_noor', N'نور الدين محمد الزعبي', N'COURT_CLERK', N'كاتب محكمة', 1, 1),
(N'TEST-NID-9903003002', N'judge_adel', N'القاضي عادل إبراهيم الحسن', N'COURT_JUDGE', N'قاضٍ', 1, 1),
(N'TEST-NID-9904004001', N'land_officer_rami', N'رامي سعيد البطاينة', N'LAND_OFFICER', N'موظف دائرة الأراضي', 2, 1),
(N'TEST-NID-9905005001', N'civil_officer_dana', N'دانة يوسف الكردي', N'CIVIL_STATUS_OFFICER', N'موظف الأحوال المدنية', 3, 1),
(N'TEST-NID-9906006001', N'gov_tax_fadi', N'فادي سالم القيسي', N'GOV_ENTITY_OFFICER', N'موظف جهة حكومية', 4, 1),
(N'TEST-NID-9906006002', N'gov_gam_hana', N'هناء محمود الرواشدة', N'GOV_ENTITY_OFFICER', N'موظف جهة حكومية', 8, 1);
GO

-- 3. إدخال القضايا (cases)
INSERT INTO cases (
    case_number, court_name, court_type_ar, court_location_ar,
    case_type, case_type_ar, case_year, registry_type, registry_type_ar,
    opened_date, case_status, case_status_ar,
    citizen_user_id, lawyer_user_id, public_summary_ar, party_search_type_ar
)
VALUES
(
    N'2026-CIV-1041', N'محكمة بداية حقوق عمّان', N'محكمة بداية', N'عمّان - العبدلي',
    N'REAL_ESTATE', N'عقارية', 2026, N'BIDAYAH', N'بداية',
    N'2026-02-10', N'WAITING_FOR_DOCUMENTS', N'بانتظار وثائق من الجهات',
    1, 3, N'دعوى إثبات ملكية وحقوق ارتفاق لقطعة أرض في عمّان.', N'بحث بالرقم الوطني / اسم الطرف'
),
(
    N'2026-CIV-2088', N'محكمة صلح حقوق عمّان', N'محكمة صلح', N'عمّان - وسط البلد',
    N'CIVIL', N'حقوقية مدنية', 2026, N'SULH', N'صلح',
    N'2026-04-05', N'IN_PROGRESS', N'قيد المتابعة والإجراءات',
    2, 4, N'مطالبة مالية وتدقيق بيانات سجل وعنوان طرف الدعوى.', N'بحث باسم الطرف / المؤسسة'
);
GO

-- 4. إدخال أطراف القضايا (case_parties)
INSERT INTO case_parties (
    case_id, user_id, party_role, party_role_ar, is_primary,
    party_name_ar, party_identifier, institution_name_ar, party_category, party_category_ar
)
VALUES
(1, 1, N'CLAIMANT', N'مدّعٍ', 1, N'طارق محمود العبدالله', N'TEST-NID-9901001001', NULL, N'PERSON', N'شخص طبيعي'),
(1, 3, N'AUTHORIZED_LAWYER', N'وكيل بالخصومة', 0, N'المحامي عمر خالد الطراونة', N'TEST-NID-9902002001', NULL, N'PERSON', N'شخص طبيعي'),
(1, NULL, N'DEFENDANT', N'مدّعى عليه', 0, N'شركة البناء الحديث للتطوير', N'TEST-INST-501', N'شركة البناء الحديث للتطوير', N'INSTITUTION', N'مؤسسة / شركة'),
(2, 2, N'CLAIMANT', N'مدّعية', 1, N'ليلى حسن النابلسي', N'TEST-NID-9901001002', NULL, N'PERSON', N'شخص طبيعي'),
(2, 4, N'AUTHORIZED_LAWYER', N'وكيلة بالخصومة', 0, N'المحامية سارة أحمد المجالي', N'TEST-NID-9902002002', NULL, N'PERSON', N'شخص طبيعي');
GO

-- 5. إدخال طلبات الكتب / سجل الكتب (document_requests)
INSERT INTO document_requests (
    case_id, requested_by_user_id, target_entity_id, request_type, request_title_ar,
    request_status, court_decision_by_user_id, court_decision_at,
    sent_to_entity_at, response_received_at, delay_days, delay_reason_code,
    public_status_message_ar, internal_note
)
VALUES
(
    1, 3, 2, N'LAND_OWNERSHIP_EXTRACT', N'طلب مخطط أراضي ومستند ملكية لقطعة رقم 45',
    N'RESPONSE_RECEIVED', 6, N'2026-03-02 10:30:00',
    N'2026-03-03 08:15:00', N'2026-03-12 13:45:00', 0, NULL,
    N'تم استلام رد دائرة الأراضي وإرفاقه بملف الدعوى.', N'الرد مطابق للبيانات المساحية المرفقة.'
),
(
    1, 3, 8, N'ZONING_STATUS_LETTER', N'طلب بيان تنظيم وموافقة بلدية لموقع العقار',
    N'DELAYED', 6, N'2026-05-10 11:00:00',
    N'2026-05-11 09:00:00', NULL, 6, N'ENTITY_QUEUE_BACKLOG',
    N'الكتاب مرسل إلى أمانة عمّان الكبرى وقيد المعالجة مع تأخير إداري.', N'تم إرسال تنبيه متابعة للجهة.'
),
(
    2, 4, 3, N'CIVIL_RECORD_CHECK', N'طلب قيد فردي ومطابقة بيانات هوية',
    N'APPROVED', 6, N'2026-06-15 09:40:00',
    NULL, NULL, 0, NULL,
    N'تمت موافقة المحكمة على الكتاب وجارٍ إرساله للأحوال المدنية.', N'جاهز للإرسال الإلكتروني.'
);
GO

-- 6. إدخال المستندات والمرفقات (documents)
INSERT INTO documents (
    request_id, document_type, document_type_ar, document_title_ar, file_name,
    uploaded_by_user_id, visibility, visibility_ar,
    is_printable_by_citizen, is_official, document_status, document_status_ar,
    print_permission_note_ar, attachment_notes_ar, attachment_action_ar
)
VALUES
(
    1, N'LAWYER_REQUEST_PDF', N'نسخة PDF لطلب المحامي', N'طلب كتاب دائرة الأراضي - نسخة مقدم الطلب', N'req_1041_dls_request_test.pdf',
    3, N'COURT_AND_AUTHORIZED_LAWYER', N'المحكمة والمحامي الموكل فقط',
    0, 0, N'UPLOADED', N'مرفوع',
    N'غير متاح للطباعة للمواطن', N'مرفق رقمي تجريبي أولي', N'معاينة'
),
(
    1, N'ENTITY_RESPONSE', N'رد الجهة الحكومية', N'مخطط أراضي ومستند ملكية صادر عن دائرة الأراضي', N'resp_1041_dls_extract_test.pdf',
    7, N'CITIZEN_AND_LAWYER', N'المواطن والمحامي الموكل',
    1, 1, N'RECEIVED', N'مستلم',
    N'متاح للطباعة للمواطن والمحامي', N'وثيقة تجريبية تمثل رد الجهة المختصة', N'تنزيل وطباعة'
),
(
    2, N'PUBLIC_STATUS_CERTIFICATE', N'شهادة حالة عامة', N'إشعار متابعة طلب بيان التنظيم', N'status_1041_gam_notice_test.pdf',
    5, N'CITIZEN_AND_LAWYER', N'المواطن والمحامي الموكل',
    1, 0, N'AVAILABLE', N'متاح',
    N'متاح للطباعة للمواطن', N'إشعار حالة تجريبي يوضح تأخر الرد', N'عرض الحالة'
);
GO

-- 7. إدخال الخط الزمني للطلبات (request_timeline)
INSERT INTO request_timeline (request_id, event_code, event_description_ar, actor_user_id, is_visible_to_citizen)
VALUES
(1, N'REQUEST_SUBMITTED', N'قدّم المحامي طلب كتاب إلى دائرة الأراضي والمساحة.', 3, 1),
(1, N'COURT_APPROVED', N'وافق القاضي على إرسال الكتاب إلى دائرة الأراضي.', 6, 1),
(1, N'ENTITY_RESPONSE_RECEIVED', N'وردت إجابة دائرة الأراضي وتمت إتاحتها في ملف الطلب.', 7, 1),
(2, N'REQUEST_DELAYED', N'تجاوز الطلب المدة المعتادة لدى الجهة وتم تسجيل تأخير 6 أيام.', 10, 1);
GO

-- 8. إدخال سجل التدقيق (audit_logs)
INSERT INTO audit_logs (actor_user_id, case_id, request_id, action_code, result, details)
VALUES
(3, 1, 1, N'CREATE_DOCUMENT_REQUEST', N'SUCCESS', N'إنشاء طلب كتاب جديد موجه لدائرة الأراضي على القضية 2026-CIV-1041.'),
(6, 1, 1, N'APPROVE_DOCUMENT_REQUEST', N'SUCCESS', N'اعتماد طلب الكتاب رقم 1 من قبل القاضي.'),
(7, 1, 1, N'UPLOAD_ENTITY_RESPONSE', N'SUCCESS', N'رفع رد دائرة الأراضي على الطلب رقم 1.'),
(1, 2, NULL, N'VIEW_CASE_SUMMARY', N'SUCCESS', N'استعلام المواطن عن ملخص القضية 2026-CIV-2088.');
GO

-- 9. إدخال الإشعارات (notifications)
INSERT INTO notifications (user_id, request_id, notification_type, notification_type_ar, message_ar, is_read)
VALUES
(1, 1, N'RESPONSE_AVAILABLE', N'وصول رد جهة', N'تم استلام رد دائرة الأراضي على طلب الكتاب الخاص بقضيتك رقم 2026-CIV-1041.', 0),
(3, 2, N'REQUEST_DELAYED', N'تنبيه تأخير طلب', N'سُجل تأخير 6 أيام على طلب بيان التنظيم المرسل إلى أمانة عمّان الكبرى.', 0),
(4, 3, N'REQUEST_APPROVED', N'اعتماد طلب كتاب', N'تمت موافقة المحكمة على طلب القيد الفردي للقضية رقم 2026-CIV-2088.', 1);
GO

-- 10. إدخال صلاحيات المستندات (document_permissions)
INSERT INTO document_permissions (role, document_type, can_view, can_download, can_print)
VALUES
(N'CITIZEN', N'LAWYER_REQUEST_PDF', 0, 0, 0),
(N'CITIZEN', N'ENTITY_RESPONSE', 1, 1, 1),
(N'CITIZEN', N'PUBLIC_STATUS_CERTIFICATE', 1, 1, 1),
(N'LAWYER', N'LAWYER_REQUEST_PDF', 1, 1, 1),
(N'LAWYER', N'ENTITY_RESPONSE', 1, 1, 1),
(N'LAWYER', N'PUBLIC_STATUS_CERTIFICATE', 1, 1, 1),
(N'COURT_CLERK', N'LAWYER_REQUEST_PDF', 1, 1, 0),
(N'COURT_CLERK', N'ENTITY_RESPONSE', 1, 1, 0),
(N'COURT_CLERK', N'PUBLIC_STATUS_CERTIFICATE', 1, 1, 1),
(N'COURT_JUDGE', N'LAWYER_REQUEST_PDF', 1, 1, 0),
(N'COURT_JUDGE', N'ENTITY_RESPONSE', 1, 1, 0),
(N'COURT_JUDGE', N'PUBLIC_STATUS_CERTIFICATE', 1, 0, 0),
(N'LAND_OFFICER', N'ENTITY_RESPONSE', 1, 1, 0),
(N'CIVIL_STATUS_OFFICER', N'ENTITY_RESPONSE', 1, 1, 0),
(N'GOV_ENTITY_OFFICER', N'ENTITY_RESPONSE', 1, 1, 0);
GO
