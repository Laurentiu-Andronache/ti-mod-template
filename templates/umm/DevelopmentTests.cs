#if TI_MOD_TESTS
// This type is absent from ordinary Release builds. Each public static,
// parameterless method is one development test returning a JSON object.
namespace __MOD_ID__
{
    public static class DevelopmentTests
    {
        public static string Probe()
        {
            bool previous = Main.Settings.PatchProbe;
            try
            {
                Main.Settings.PatchProbe = true;
                string patched = __MOD_ID__.Probe.Message();
                Main.Settings.PatchProbe = false;
                string original = __MOD_ID__.Probe.Message();
                bool pass = Main.Enabled && patched == "patched" && original == "original";
                return "{\"passed\":" + (pass ? "true" : "false") +
                       ",\"patched\":\"" + patched + "\",\"original\":\"" + original + "\"}";
            }
            finally { Main.Settings.PatchProbe = previous; }
        }
    }
}
#endif
