-- ============================================================================
-- قاعدة بيانات منصة تبادل الكتب القضائية - SQL Server (T-SQL)
-- الجداول الـ 10 كاملة مع المفاتيح الأساسية والأجنبية والقيود (Constraints)
-- معتمدة على الرقم الوطني (national_id) واسم المستخدم (username) بدون بريد إلكتروني
-- ============================================================================

CREATE DATABASE JudicialExchangeDB;
GO
USE JudicialExchangeDB;
GO

-- 1. جدول الجهات الحكومية والقضائية (government_entities)
CREATE TABLE government_entities (
    entity_id INT IDENTITY(1,1) PRIMARY KEY,
    entity_code NVARCHAR(40) NOT NULL UNIQUE,
    entity_name_ar NVARCHAR(180) NOT NULL,
    entity_name_en NVARCHAR(180) NOT NULL,
    entity_type NVARCHAR(20) NOT NULL CHECK (entity_type IN ('JUDICIAL', 'GOVERNMENT')),
    is_active BIT NOT NULL DEFAULT 1
);
GO

-- 2. جدول المستخدمين (users) - الرقم الوطني واسم المستخدم أساسيان
CREATE TABLE users (
    user_id INT IDENTITY(1,1) PRIMARY KEY,
    national_id NVARCHAR(30) NOT NULL UNIQUE,
    username NVARCHAR(80) NOT NULL UNIQUE,
    display_name NVARCHAR(150) NOT NULL,
    role NVARCHAR(40) NOT NULL CHECK (role IN (
        'CITIZEN',
        'LAWYER',
        'COURT_CLERK',
        'COURT_JUDGE',
        'LAND_OFFICER',
        'CIVIL_STATUS_OFFICER',
        'GOV_ENTITY_OFFICER'
    )),
    role_ar NVARCHAR(80) NOT NULL,
    entity_id INT NULL,
    is_active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT fk_users_entity FOREIGN KEY (entity_id) REFERENCES government_entities(entity_id)
);
GO

-- 3. جدول القضايا (cases)
CREATE TABLE cases (
    case_id INT IDENTITY(1,1) PRIMARY KEY,
    case_number NVARCHAR(40) NOT NULL UNIQUE,
    court_name NVARCHAR(180) NOT NULL,
    court_type_ar NVARCHAR(80) NOT NULL,
    court_location_ar NVARCHAR(100) NOT NULL,
    case_type NVARCHAR(30) NOT NULL CHECK (case_type IN (
        'REAL_ESTATE', 'CIVIL', 'INHERITANCE', 'ADMINISTRATIVE', 'PERSONAL_STATUS'
    )),
    case_type_ar NVARCHAR(100) NOT NULL,
    case_year SMALLINT NOT NULL CHECK (case_year >= 1900),
    registry_type NVARCHAR(20) NOT NULL CHECK (registry_type IN ('BIDAYAH', 'SULH', 'APPEAL')),
    registry_type_ar NVARCHAR(80) NOT NULL,
    opened_date DATE NOT NULL,
    case_status NVARCHAR(30) NOT NULL CHECK (case_status IN (
        'REGISTERED', 'IN_PROGRESS', 'WAITING_FOR_DOCUMENTS', 'UNDER_REVIEW', 'COMPLETED'
    )),
    case_status_ar NVARCHAR(100) NOT NULL,
    citizen_user_id INT NOT NULL,
    lawyer_user_id INT NOT NULL,
    public_summary_ar NVARCHAR(500) NOT NULL,
    party_search_type_ar NVARCHAR(100) NULL,
    last_updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT fk_cases_citizen FOREIGN KEY (citizen_user_id) REFERENCES users(user_id),
    CONSTRAINT fk_cases_lawyer FOREIGN KEY (lawyer_user_id) REFERENCES users(user_id)
);
GO

CREATE INDEX idx_cases_status ON cases(case_status);
GO

-- 4. جدول أطراف القضايا (case_parties)
CREATE TABLE case_parties (
    case_party_id INT IDENTITY(1,1) PRIMARY KEY,
    case_id INT NOT NULL,
    user_id INT NULL,
    party_role NVARCHAR(30) NOT NULL CHECK (party_role IN (
        'CLAIMANT', 'DEFENDANT', 'AUTHORIZED_LAWYER', 'OTHER'
    )),
    party_role_ar NVARCHAR(80) NOT NULL,
    is_primary BIT NOT NULL DEFAULT 0,
    party_name_ar NVARCHAR(180) NOT NULL,
    party_identifier NVARCHAR(60) NULL,
    institution_name_ar NVARCHAR(180) NULL,
    party_category NVARCHAR(20) NOT NULL DEFAULT 'PERSON' CHECK (party_category IN ('PERSON', 'INSTITUTION')),
    party_category_ar NVARCHAR(80) NOT NULL,
    CONSTRAINT uq_case_user_role UNIQUE (case_id, user_id, party_role),
    CONSTRAINT fk_case_parties_case FOREIGN KEY (case_id) REFERENCES cases(case_id),
    CONSTRAINT fk_case_parties_user FOREIGN KEY (user_id) REFERENCES users(user_id)
);
GO

-- 5. جدول طلبات الكتب / سجل الكتب (document_requests)
CREATE TABLE document_requests (
    request_id INT IDENTITY(1,1) PRIMARY KEY,
    case_id INT NOT NULL,
    requested_by_user_id INT NOT NULL,
    target_entity_id INT NOT NULL,
    request_type NVARCHAR(60) NOT NULL,
    request_title_ar NVARCHAR(220) NOT NULL,
    request_status NVARCHAR(40) NOT NULL CHECK (request_status IN (
        'DRAFT',
        'SUBMITTED',
        'UNDER_COURT_REVIEW',
        'APPROVED',
        'REJECTED',
        'SENT_TO_ENTITY',
        'UNDER_PROCESSING',
        'DELAYED',
        'RESPONSE_RECEIVED',
        'RETURNED_FOR_MODIFICATION'
    )),
    submitted_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    court_decision_by_user_id INT NULL,
    court_decision_at DATETIME2 NULL,
    sent_to_entity_at DATETIME2 NULL,
    response_received_at DATETIME2 NULL,
    delay_days INT NOT NULL DEFAULT 0 CHECK (delay_days >= 0),
    delay_reason_code NVARCHAR(60) NULL,
    public_status_message_ar NVARCHAR(500) NOT NULL,
    internal_note NVARCHAR(1000) NULL,
    CONSTRAINT fk_requests_case FOREIGN KEY (case_id) REFERENCES cases(case_id),
    CONSTRAINT fk_requests_requester FOREIGN KEY (requested_by_user_id) REFERENCES users(user_id),
    CONSTRAINT fk_requests_entity FOREIGN KEY (target_entity_id) REFERENCES government_entities(entity_id),
    CONSTRAINT fk_requests_decision_user FOREIGN KEY (court_decision_by_user_id) REFERENCES users(user_id)
);
GO

CREATE INDEX idx_requests_case ON document_requests(case_id);
CREATE INDEX idx_requests_status ON document_requests(request_status);
CREATE INDEX idx_requests_entity_status ON document_requests(target_entity_id, request_status);
GO

-- 6. جدول المستندات والمرفقات (documents)
CREATE TABLE documents (
    document_id INT IDENTITY(1,1) PRIMARY KEY,
    request_id INT NOT NULL,
    document_type NVARCHAR(40) NOT NULL CHECK (document_type IN (
        'LAWYER_REQUEST_PDF', 'ENTITY_RESPONSE', 'PUBLIC_STATUS_CERTIFICATE'
    )),
    document_type_ar NVARCHAR(220) NOT NULL,
    document_title_ar NVARCHAR(220) NOT NULL,
    file_name NVARCHAR(255) NOT NULL,
    uploaded_by_user_id INT NOT NULL,
    visibility NVARCHAR(40) NOT NULL CHECK (visibility IN (
        'AUTHORIZED_PARTIES', 'COURT_AND_AUTHORIZED_LAWYER', 'CITIZEN_AND_LAWYER'
    )),
    visibility_ar NVARCHAR(120) NOT NULL,
    is_printable_by_citizen BIT NOT NULL DEFAULT 0,
    is_official BIT NOT NULL DEFAULT 0,
    document_status NVARCHAR(20) NOT NULL CHECK (document_status IN (
        'UPLOADED', 'RECEIVED', 'AVAILABLE', 'REVOKED'
    )),
    document_status_ar NVARCHAR(80) NOT NULL,
    print_permission_note_ar NVARCHAR(180) NULL,
    attachment_notes_ar NVARCHAR(500) NULL,
    attachment_action_ar NVARCHAR(100) NULL,
    uploaded_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT fk_documents_request FOREIGN KEY (request_id) REFERENCES document_requests(request_id),
    CONSTRAINT fk_documents_uploader FOREIGN KEY (uploaded_by_user_id) REFERENCES users(user_id),
    CONSTRAINT chk_citizen_print_visibility CHECK (
        is_printable_by_citizen = 0 OR visibility = 'CITIZEN_AND_LAWYER'
    )
);
GO

CREATE INDEX idx_documents_request ON documents(request_id);
GO

-- 7. جدول الخط الزمني للطلبات (request_timeline)
CREATE TABLE request_timeline (
    timeline_id INT IDENTITY(1,1) PRIMARY KEY,
    request_id INT NOT NULL,
    event_code NVARCHAR(60) NOT NULL,
    event_description_ar NVARCHAR(300) NOT NULL,
    actor_user_id INT NOT NULL,
    event_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    is_visible_to_citizen BIT NOT NULL DEFAULT 0,
    CONSTRAINT fk_timeline_request FOREIGN KEY (request_id) REFERENCES document_requests(request_id),
    CONSTRAINT fk_timeline_actor FOREIGN KEY (actor_user_id) REFERENCES users(user_id)
);
GO

CREATE INDEX idx_timeline_request_date ON request_timeline(request_id, event_at);
GO

-- 8. جدول سجل التدقيق (audit_logs)
CREATE TABLE audit_logs (
    audit_id INT IDENTITY(1,1) PRIMARY KEY,
    actor_user_id INT NOT NULL,
    case_id INT NOT NULL,
    request_id INT NULL,
    action_code NVARCHAR(80) NOT NULL,
    action_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    result NVARCHAR(20) NOT NULL CHECK (result IN ('SUCCESS', 'FAILURE')),
    details NVARCHAR(500) NOT NULL,
    CONSTRAINT fk_audit_actor FOREIGN KEY (actor_user_id) REFERENCES users(user_id),
    CONSTRAINT fk_audit_case FOREIGN KEY (case_id) REFERENCES cases(case_id),
    CONSTRAINT fk_audit_request FOREIGN KEY (request_id) REFERENCES document_requests(request_id)
);
GO

CREATE INDEX idx_audit_case_date ON audit_logs(case_id, action_at);
CREATE INDEX idx_audit_request_date ON audit_logs(request_id, action_at);
GO

-- 9. جدول الإشعارات (notifications)
CREATE TABLE notifications (
    notification_id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL,
    request_id INT NOT NULL,
    notification_type NVARCHAR(60) NOT NULL,
    notification_type_ar NVARCHAR(120) NOT NULL,
    message_ar NVARCHAR(500) NOT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    is_read BIT NOT NULL DEFAULT 0,
    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT fk_notifications_request FOREIGN KEY (request_id) REFERENCES document_requests(request_id)
);
GO

CREATE INDEX idx_notifications_user_read ON notifications(user_id, is_read);
GO

-- 10. جدول صلاحيات المستندات (document_permissions)
CREATE TABLE document_permissions (
    permission_id INT IDENTITY(1,1) PRIMARY KEY,
    role NVARCHAR(40) NOT NULL CHECK (role IN (
        'CITIZEN',
        'LAWYER',
        'COURT_CLERK',
        'COURT_JUDGE',
        'LAND_OFFICER',
        'CIVIL_STATUS_OFFICER',
        'GOV_ENTITY_OFFICER'
    )),
    document_type NVARCHAR(40) NOT NULL CHECK (document_type IN (
        'LAWYER_REQUEST_PDF', 'ENTITY_RESPONSE', 'PUBLIC_STATUS_CERTIFICATE'
    )),
    can_view BIT NOT NULL DEFAULT 0,
    can_download BIT NOT NULL DEFAULT 0,
    can_print BIT NOT NULL DEFAULT 0,
    CONSTRAINT uq_role_document UNIQUE (role, document_type),
    CONSTRAINT chk_permission_consistency CHECK (
        (can_print = 0 OR can_download = 1) AND
        (can_download = 0 OR can_view = 1)
    )
);
GO
