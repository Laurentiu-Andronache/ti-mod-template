using System;
using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using UnityEngine;
using UnityModManagerNet;

namespace __MOD_ID__
{
    // Adapted from the MIT ti-mods starter; see THIRD_PARTY_NOTICES.md.
    public static class Main
    {
        internal static bool Enabled;
        internal static Settings Settings;
        private static Harmony harmony;

        public static bool Load(UnityModManager.ModEntry entry)
        {
            try
            {
                Settings = UnityModManager.ModSettings.Load<Settings>(entry);
                harmony = new Harmony(entry.Info.Id);
                entry.OnToggle = OnToggle;
                entry.OnUnload = e => OnToggle(e, false);
                entry.OnGUI = OnGUI;
                entry.OnSaveGUI = e => Settings.Save(e);
                entry.Logger.Log("Loaded; the starter changes no campaign data.");
                return true;
            }
            catch (Exception exception)
            {
                entry.Logger.Error(exception.ToString());
                return false;
            }
        }

        private static bool OnToggle(UnityModManager.ModEntry entry, bool value)
        {
            if (Enabled == value) return true;
            try
            {
                if (value)
                {
                    harmony.PatchAll(Assembly.GetExecutingAssembly());
                    Enabled = true;
                }
                else
                {
                    Enabled = false;
                    harmony.UnpatchAll(entry.Info.Id);
                }
                entry.Logger.Log("Enabled=" + Enabled + "; Probe=" + Probe.Message());
                return true;
            }
            catch (Exception exception)
            {
                Enabled = false;
                harmony.UnpatchAll(entry.Info.Id);
                entry.Logger.Error(exception.ToString());
                return false;
            }
        }

        private static void OnGUI(UnityModManager.ModEntry entry)
        {
            GUILayout.Label("Harmony probe: " + Probe.Message());
            Settings.PatchProbe = GUILayout.Toggle(Settings.PatchProbe, "Enable starter probe");
        }
    }

    public sealed class Settings : UnityModManager.ModSettings
    {
        public bool PatchProbe = true;
        public override void Save(UnityModManager.ModEntry entry) { Save(this, entry); }
    }

    internal static class Probe
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        internal static string Message() { return "original"; }
    }

    [HarmonyPatch(typeof(Probe), nameof(Probe.Message))]
    internal static class ProbePatch
    {
        private static void Postfix(ref string __result)
        {
            if (Main.Enabled && Main.Settings.PatchProbe) __result = "patched";
        }
    }
}
