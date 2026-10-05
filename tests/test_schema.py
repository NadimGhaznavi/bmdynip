"""Check the schema against an explicitly supplied disposable MariaDB socket."""

import os
from pathlib import Path
import subprocess
import unittest
from uuid import uuid4


@unittest.skipUnless(os.environ.get("BMDYNIP_TEST_DB_SOCKET"),
                     "Set BMDYNIP_TEST_DB_SOCKET for database checks")
class SchemaTests(unittest.TestCase):
    def sql(self, statement, *, error=None):
        result = subprocess.run(
            ["mariadb", "--no-defaults", "--protocol=socket",
             "--socket=" + os.environ["BMDYNIP_TEST_DB_SOCKET"],
             "--user=root", "--batch", "--skip-column-names"],
            input=statement, text=True, capture_output=True, timeout=15,
        )
        if error is None:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ERROR " + str(error), result.stderr)
        return result.stdout.strip()

    def query(self, statement, **kwargs):
        return self.sql(f"USE `{self.database}`;\n" + statement, **kwargs)

    def setUp(self):
        self.database = "bmdynip_test_" + uuid4().hex
        self.sql(f"CREATE DATABASE `{self.database}`;")
        self.addCleanup(self.sql, f"DROP DATABASE `{self.database}`;")
        self.schema = (Path(__file__).resolve().parents[1] /
                       "schema/bmdynip-schema-v1.sql").read_text()
        self.query(self.schema)
        self.query("""
            INSERT INTO ModelElement (id, name) VALUES
                (1, 'router'), (2, 'upstream'), (3, 'software'), (4, 'component');
            INSERT INTO Namespace (id) VALUES (1), (2), (3), (4);
            INSERT INTO Machine (id, ipAddress) VALUES (1, '192.0.2.1'), (2, '192.0.2.2');
            INSERT INTO Package (id) VALUES (3);
            INSERT INTO SoftwareSystem (id) VALUES (3);
            UPDATE ModelElement SET namespace=3 WHERE id=4;
            INSERT INTO Component (id) VALUES (4);
            INSERT INTO ModelElement (id, name, namespace) VALUES
                (5, 'router client', 1), (6, 'TekSavvy', 2);
            INSERT INTO Namespace (id) VALUES (5), (6);
            INSERT INTO Package (id) VALUES (5), (6);
            INSERT INTO DeployedComponent (id, pathname, machine, component)
                VALUES (5, '/', 1, 4), (6, '/', 2, 4);
            INSERT INTO DataManager (id) VALUES (5), (6);
            INSERT INTO DataProvider (id) VALUES (5);
            INSERT INTO ModelElement (id, name, namespace) VALUES (7, 'WAN', 5);
            INSERT INTO ProviderConnection (id, isReadOnly, dataProvider, dataManager)
                VALUES (7, FALSE, 5, 6);
        """)

    def request(self, identity=8):
        self.query(f"""
            INSERT INTO ModelElement (id) VALUES ({identity});
            INSERT INTO ChangeRequest
                (id, changeDescription, changeReason, status, requestDate)
                VALUES ({identity}, 'Address changed', 'Discovery', 'proposed', UTC_TIMESTAMP(6));
            INSERT INTO ModelElementChangeRequest (modelElement, changeRequest, position)
                VALUES (7, {identity}, {identity});
            INSERT INTO TaggedValue (tag, value, modelElement)
                VALUES ('hostname', 'wintermute.example.com', {identity});
        """)

    def test_schema_reapplication_preserves_records_and_table_names(self):
        self.request()
        self.query(self.schema)
        self.assertEqual(set(self.query("SHOW TABLES;").splitlines()), {
            "ModelElement", "Namespace", "Package", "TaggedValue", "Machine",
            "SoftwareSystem", "Component", "DeployedComponent", "DataManager",
            "DataProvider", "ProviderConnection", "ChangeRequest",
            "ModelElementChangeRequest", "DnsRecord", "ApplicationMigration",
        })
        self.assertEqual(self.query("SELECT COUNT(*) FROM ChangeRequest;"), "1")

    def test_deployment_and_connection_ownership_and_endpoints(self):
        self.query("UPDATE DeployedComponent SET machine=2 WHERE id=5;", error=1452)
        self.query("UPDATE ModelElement SET namespace=6 WHERE id=7;", error=1451)
        self.query("UPDATE ProviderConnection SET dataManager=5 WHERE id=7;", error=4025)
        self.query("UPDATE ProviderConnection SET dataManager=999 WHERE id=7;", error=1452)
        self.query("UPDATE ProviderConnection SET isReadOnly=2 WHERE id=7;", error=4025)

    def test_request_constraints_and_ordered_many_valued_association(self):
        self.request()
        self.request(9)
        self.query("INSERT INTO ModelElementChangeRequest VALUES (6, 8, 1);")
        self.query("INSERT INTO ModelElementChangeRequest VALUES (8, 8, 1);", error=4025)
        self.query("UPDATE ModelElementChangeRequest SET position=8 "
                   "WHERE modelElement=7 AND changeRequest=9;", error=1062)
        self.query("UPDATE ChangeRequest SET completionDate=UTC_TIMESTAMP(6) WHERE id=8;",
                   error=4025)
        self.query("UPDATE ChangeRequest SET completed=2 WHERE id=8;", error=4025)
        self.query("UPDATE ChangeRequest SET completed=TRUE, status='implemented', "
                   "completionDate=UTC_TIMESTAMP(6) WHERE id=8;")
        self.assertEqual(self.query("SELECT changeRequest FROM ModelElementChangeRequest "
                                    "WHERE modelElement=7 ORDER BY position;"), "8\n9")

    def test_dns_removal_preserves_history_and_tags_are_unique_and_case_sensitive(self):
        self.request()
        self.query("INSERT INTO DnsRecord (domain, name) VALUES ('example.com', 'wintermute');")
        self.query("INSERT INTO DnsRecord (domain, name) VALUES ('example.com', 'wintermute');",
                   error=1062)
        self.query("INSERT INTO TaggedValue (tag, value, modelElement) "
                   "VALUES ('hostname', 'other.example.com', 8);", error=1062)
        self.query("INSERT INTO TaggedValue (tag, value, modelElement) "
                   "VALUES ('Hostname', 'distinct tag', 8);")
        self.query("DELETE FROM DnsRecord;")
        self.assertEqual(self.query("SELECT value FROM TaggedValue "
                                    "WHERE modelElement=8 AND tag='hostname';"),
                         "wintermute.example.com")
        self.query("DELETE FROM ProviderConnection WHERE id=7;")
        self.query("DELETE FROM ModelElement WHERE id=7;", error=1451)

    def test_related_writes_roll_back_on_failure(self):
        self.query("""
            START TRANSACTION;
            INSERT INTO ModelElement (id) VALUES (8);
            INSERT INTO ChangeRequest
                (id, changeDescription, changeReason, status, requestDate)
                VALUES (8, 'Change', 'Discovery', 'proposed', UTC_TIMESTAMP(6));
            INSERT INTO ModelElementChangeRequest VALUES (999, 8, 1);
            COMMIT;
        """, error=1452)
        self.assertEqual(self.query("SELECT COUNT(*) FROM ModelElement WHERE id=8;"), "0")
        self.assertEqual(self.query("SELECT COUNT(*) FROM ChangeRequest;"), "0")
