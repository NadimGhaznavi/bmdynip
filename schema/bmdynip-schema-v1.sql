-- Adopted CWM classes and associations, followed by application-specific tables.
CREATE TABLE IF NOT EXISTS ModelElement (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) COLLATE utf8mb4_bin NULL,
    namespace BIGINT UNSIGNED NULL,
    UNIQUE KEY ModelElement_id_namespace_uq (id, namespace)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Namespace (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    CONSTRAINT Namespace_ModelElement_fk FOREIGN KEY (id) REFERENCES ModelElement (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Package (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    CONSTRAINT Package_Namespace_fk FOREIGN KEY (id) REFERENCES Namespace (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS TaggedValue (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tag VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    value TEXT NOT NULL,
    modelElement BIGINT UNSIGNED NULL,
    UNIQUE KEY TaggedValue_modelElement_tag_uq (modelElement, tag),
    CONSTRAINT TaggedValue_ModelElement_fk FOREIGN KEY (modelElement) REFERENCES ModelElement (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Complete the parent reference after both tables exist. This is not a data migration.
ALTER TABLE ModelElement
    ADD FOREIGN KEY IF NOT EXISTS ModelElement_namespace_fk (namespace) REFERENCES Namespace (id);

CREATE TABLE IF NOT EXISTS Machine (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    ipAddress VARCHAR(45) NOT NULL,
    hostName VARCHAR(255) NULL,
    macAddress VARCHAR(17) NULL,
    site VARCHAR(255) NULL,
    createdOn TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updatedOn TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY Machine_ipAddress_uq (ipAddress),
    CONSTRAINT Machine_Namespace_fk FOREIGN KEY (id) REFERENCES Namespace (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS SoftwareSystem (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    type VARCHAR(255) NULL,
    subtype VARCHAR(255) NULL,
    supplier VARCHAR(255) NULL,
    version VARCHAR(255) NULL,
    CONSTRAINT SoftwareSystem_Package_fk FOREIGN KEY (id) REFERENCES Package (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Component (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    CONSTRAINT Component_Namespace_fk FOREIGN KEY (id) REFERENCES Namespace (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS DeployedComponent (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    pathname TEXT NOT NULL,
    machine BIGINT UNSIGNED NOT NULL,
    component BIGINT UNSIGNED NOT NULL,
    CONSTRAINT DeployedComponent_Package_fk FOREIGN KEY (id) REFERENCES Package (id),
    -- The explicit machine reference must equal the inherited owner.
    CONSTRAINT DeployedComponent_owner_fk
        FOREIGN KEY (id, machine) REFERENCES ModelElement (id, namespace),
    CONSTRAINT DeployedComponent_machine_fk FOREIGN KEY (machine) REFERENCES Machine (id),
    CONSTRAINT DeployedComponent_component_fk FOREIGN KEY (component) REFERENCES Component (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS DataManager (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    CONSTRAINT DataManager_DeployedComponent_fk FOREIGN KEY (id) REFERENCES DeployedComponent (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS DataProvider (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    CONSTRAINT DataProvider_DataManager_fk FOREIGN KEY (id) REFERENCES DataManager (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ProviderConnection (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    isReadOnly BOOLEAN NOT NULL,
    dataProvider BIGINT UNSIGNED NOT NULL,
    dataManager BIGINT UNSIGNED NOT NULL,
    CONSTRAINT ProviderConnection_ModelElement_fk FOREIGN KEY (id) REFERENCES ModelElement (id),
    CONSTRAINT ProviderConnection_owner_fk
        FOREIGN KEY (id, dataProvider) REFERENCES ModelElement (id, namespace),
    CONSTRAINT ProviderConnection_provider_fk FOREIGN KEY (dataProvider) REFERENCES DataProvider (id),
    CONSTRAINT ProviderConnection_manager_fk FOREIGN KEY (dataManager) REFERENCES DataManager (id),
    CONSTRAINT ProviderConnection_readOnly_ck CHECK (isReadOnly IN (0, 1)),
    CONSTRAINT ProviderConnection_endpoints_ck CHECK (dataProvider <> dataManager)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ChangeRequest (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    changeDescription TEXT NOT NULL,
    changeReason TEXT NOT NULL,
    status VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    requestDate DATETIME(6) NOT NULL,
    completionDate DATETIME(6) NULL,
    CONSTRAINT ChangeRequest_ModelElement_fk FOREIGN KEY (id) REFERENCES ModelElement (id),
    CONSTRAINT ChangeRequest_completed_ck CHECK (completed IN (0, 1)),
    CONSTRAINT ChangeRequest_completion_ck CHECK (completionDate IS NULL OR completed = TRUE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- position implements the ordered ChangeRequest collection on each ModelElement.
CREATE TABLE IF NOT EXISTS ModelElementChangeRequest (
    modelElement BIGINT UNSIGNED NOT NULL,
    changeRequest BIGINT UNSIGNED NOT NULL,
    position BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (modelElement, changeRequest),
    UNIQUE KEY ModelElementChangeRequest_order_uq (modelElement, position),
    CONSTRAINT ModelElementChangeRequest_element_fk FOREIGN KEY (modelElement) REFERENCES ModelElement (id),
    CONSTRAINT ModelElementChangeRequest_request_fk FOREIGN KEY (changeRequest) REFERENCES ChangeRequest (id),
    CONSTRAINT ModelElementChangeRequest_self_ck CHECK (modelElement <> changeRequest)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Application records have independent identities and do not inherit ModelElement.
CREATE TABLE IF NOT EXISTS DnsRecord (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    domain VARCHAR(253) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    name VARCHAR(253) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    address VARCHAR(45) NULL,
    UNIQUE KEY DnsRecord_domain_name_uq (domain, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
