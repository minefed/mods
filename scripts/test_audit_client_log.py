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

    def test_world_data_failures_are_counted_without_private_log_content(self):
        result = audit("""
[Worker/ERROR]: Couldn't load tag seasons:replaceable_by_snow as it is missing following references: minecraft:grass (from seasons)
[Worker/ERROR]: Couldn't parse element loot_tables:mtr:blocks/train_cargo_loader - Unknown registry key: private local details
[Render/ERROR]: Parsing error loading recipe alloy_forgery:glass_from_sand
[Render/WARN]: Invalid icon item stack: Unknown item ID: minecraft:basic_shower_head
[Render/WARN]: Recipe yuushya:block_blueprint (of type minecraft:crafting) not found
[Server/INFO]: PrivatePlayer[local:E:42] logged in with entity id 200 at (123.0, 64.0, 456.0)
""")
        self.assertEqual(result["resourceDiagnosticCount"], 5)
        self.assertEqual(result["worldJoinCount"], 1)
        self.assertEqual(result["resources"]["invalidRecipe"], {"alloy_forgery:glass_from_sand": 1})
        self.assertEqual(result["resources"]["invalidLootTable"], {"mtr:blocks/train_cargo_loader": 1})
        self.assertEqual(result["resources"]["missingBookRecipe"], {"yuushya:block_blueprint": 1})
        self.assertNotIn("PrivatePlayer", str(result))
        self.assertNotIn("123.0", str(result))
        self.assertNotIn("private local details", str(result))

    def test_clean_title_does_not_claim_world_coverage(self):
        result = audit("Reloading ResourceManager: vanilla, fabric\nGame took 100.0 seconds to start\n")
        self.assertEqual(result["resourceDiagnosticCount"], 0)
        self.assertEqual(result["worldJoinCount"], 0)


if __name__ == "__main__":
    unittest.main()
