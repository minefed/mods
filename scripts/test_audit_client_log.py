import unittest

from audit_client_log import audit


class ClientLogAuditTests(unittest.TestCase):
    def test_repeated_reload_diagnostics_are_counted(self):
        message = "[12:00:00] [Worker-ResourceReload-1/WARN]: Unable to load model: 'example:chair' referenced from: example:chair#facing=north: java.io.FileNotFoundException: example:models/chair.json\n"
        result = audit("Reloading ResourceManager: vanilla, fabric\n" + message * 2)
        self.assertEqual(result["reloadStarts"], 1)
        self.assertEqual(result["counts"], {"missingModel": 2})
        self.assertEqual(result["resources"]["missingModel"], {"example:chair": 2})

    def test_multiline_texture_warning_counts_model_once(self):
        result = audit("[00:00:00] [Worker/WARN]: Missing textures in model example:chair#inventory:\n    minecraft:textures/atlas/blocks.png:example:block/missing\n")
        self.assertEqual(result["resourceDiagnosticCount"], 1)
        self.assertEqual(result["resources"]["missingTexture"], {"example:chair#inventory": 1})

    def test_offline_authentication_failure_is_not_a_resource_error(self):
        result = audit("AuthenticationException: HTTP 401\nGame took 147.044 seconds to start\n")
        self.assertEqual(result["resourceDiagnosticCount"], 0)
        self.assertEqual(result["startupSeconds"], [147.044])

    def test_missing_sounds_and_unfinished_startup_remain_visible(self):
        result = audit("File mtr:sounds/absent.ogg does not exist, cannot add it to event mtr:absent\n")
        self.assertEqual(result["counts"], {"missingSound": 1})
        self.assertEqual(result["startupSeconds"], [])


if __name__ == "__main__":
    unittest.main()
