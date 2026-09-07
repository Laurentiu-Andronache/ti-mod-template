using System;
using System.Collections.Generic;
using System.Reflection;
using System.Text;
using HarmonyLib;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using PavonisInteractive.TerraInvicta.Debugging;
using PavonisInteractive.TerraInvicta.Systems.Bootstrap;
using UnityModManagerNet;

namespace TiModTemplate.DevTools
{
    public static class Main
    {
        private const string Command = "ti_dev";
        private static readonly FieldInfo CommandsField = AccessTools.Field(typeof(TerminalController), "commands");
        private static readonly Dictionary<TerminalController, CommandRegistration> Owned =
            new Dictionary<TerminalController, CommandRegistration>();
        private static Harmony harmony;
        private static UnityModManager.ModEntry entry;
        private static bool enabled;

        public static bool Load(UnityModManager.ModEntry modEntry)
        {
            entry = modEntry;
            if (CommandsField == null)
            {
                entry.Logger.Error("TerminalController.commands is missing; inspect this game version.");
                return false;
            }
            harmony = new Harmony(entry.Info.Id);
            entry.OnToggle = Toggle;
            entry.OnUnload = e => Toggle(e, false);
            return true;
        }

        private static bool Toggle(UnityModManager.ModEntry modEntry, bool value)
        {
            if (enabled == value) return true;
            try
            {
                if (value)
                {
                    enabled = true;
                    harmony.PatchAll(Assembly.GetExecutingAssembly());
                    var terminal = GlobalInstaller.container == null ? null : GlobalInstaller.container.TryResolve<Terminal>();
                    if (terminal != null && terminal.controller != null) Register(terminal.controller);
                }
                else Disable();
                return true;
            }
            catch (Exception exception)
            {
                entry.Logger.Error(exception.ToString());
                Disable();
                return false;
            }
        }

        private static void Disable()
        {
            enabled = false;
            harmony.UnpatchAll(entry.Info.Id);
            foreach (var pair in Owned)
            {
                var commands = CommandsField.GetValue(pair.Key) as Dictionary<string, CommandRegistration>;
                CommandRegistration existing;
                if (commands != null && commands.TryGetValue(Command, out existing) && ReferenceEquals(existing, pair.Value))
                    commands.Remove(Command);
            }
            Owned.Clear();
            UiProbe.Clear();
        }

        private static void Register(TerminalController controller)
        {
            if (!enabled || Owned.ContainsKey(controller)) return;
            var commands = CommandsField.GetValue(controller) as Dictionary<string, CommandRegistration>;
            if (commands == null) return;
            if (commands.ContainsKey(Command))
            {
                entry.Logger.Error("ti_dev belongs to another mod; leaving its registration intact.");
                return;
            }
            controller.RegisterCommand(Command, args =>
            {
                // One base64 JSON argument avoids the game's comma-separated argument parser.
                JObject result;
                try
                {
                    if (!enabled) throw new InvalidOperationException("Development helper is disabled.");
                    if (args == null || args.Length != 1 || string.IsNullOrWhiteSpace(args[0]))
                        throw new ArgumentException("Usage: ti_dev <base64-encoded UTF-8 JSON request>; see docs/testing.md");
                    if (args[0].Length > 32768) throw new ArgumentException("Request exceeds 32 KiB.");
                    var request = JObject.Parse(Encoding.UTF8.GetString(Convert.FromBase64String(args[0].Trim())));
                    result = Dispatch(request);
                    result["ok"] = true;
                }
                catch (Exception exception)
                {
                    var cause = exception is TargetInvocationException && exception.InnerException != null ? exception.InnerException : exception;
                    result = new JObject { ["ok"] = false, ["error"] = cause.Message };
                }
                controller.Output("TI_DEV_RESULT:" + result.ToString(Formatting.None));
            }, "Development UI and mod assertions; see ti-mod-template/docs/testing.md");
            Owned.Add(controller, commands[Command]);
            entry.Logger.Log("Registered ti_dev development command.");
        }

        private static JObject Dispatch(JObject request)
        {
            string op = (string)request["op"];
            if (op == "status") return new JObject { ["version"] = "0.1.0", ["enabled"] = enabled,
                ["initialized"] = GameControl.initialized, ["crashed"] = GameControl.handlingException };
            if (op == "roots" || op == "tree" || op == "inspect" || op == "click" || op == "fixture")
                return UiProbe.Execute(request);
            if (op == "tests" || op == "run")
            {
                string mod = (string)request["mod"];
                if (string.IsNullOrWhiteSpace(mod)) throw new ArgumentException("Supply mod assembly ID.");
                Type tests = null;
                foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
                    if (assembly.GetName().Name == mod) tests = assembly.GetType(mod + ".DevelopmentTests");
                if (tests == null) throw new ArgumentException("No development test type; compile the mod with -ModTests (recipe modTests:true). External DevTools alone does not add mod test hooks.");
                var names = new JArray();
                foreach (var method in tests.GetMethods(BindingFlags.Public | BindingFlags.Static | BindingFlags.DeclaredOnly))
                    if (method.GetParameters().Length == 0 && method.ReturnType == typeof(string)) names.Add(method.Name);
                if (op == "tests") return new JObject { ["tests"] = names };
                string name = (string)request["name"];
                var target = tests.GetMethod(name ?? "", BindingFlags.Public | BindingFlags.Static | BindingFlags.DeclaredOnly);
                if (target == null || target.GetParameters().Length != 0 || target.ReturnType != typeof(string))
                    throw new ArgumentException("Test must be a declared public static parameterless method returning JSON text.");
                return new JObject { ["test"] = name, ["result"] = JObject.Parse((string)target.Invoke(null, null)) };
            }
            throw new ArgumentException("Unknown operation: " + op);
        }

        [HarmonyPatch(typeof(Terminal), nameof(Terminal.Initialize))]
        private static class TerminalInitialized
        {
            private static void Postfix(Terminal __instance)
            {
                try { if (__instance.controller != null) Register(__instance.controller); }
                catch (Exception exception) { entry.Logger.Error(exception.ToString()); }
            }
        }
    }
}
