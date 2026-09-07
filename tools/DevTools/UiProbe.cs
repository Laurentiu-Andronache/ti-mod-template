using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace TiModTemplate.DevTools
{
    internal static class UiProbe
    {
        private static readonly Dictionary<string, GameObject> Handles = new Dictionary<string, GameObject>();
        private static GameObject fixture;
        private static int clicks;

        internal static void Clear()
        {
            Handles.Clear();
            if (fixture != null) UnityEngine.Object.Destroy(fixture);
            fixture = null;
        }

        private static string Remember(GameObject gameObject)
        {
            if (Handles.Count >= 512) Handles.Clear();
            string handle = Guid.NewGuid().ToString("N");
            Handles.Add(handle, gameObject);
            return handle;
        }

        private static GameObject Resolve(string handle)
        {
            GameObject found;
            if (handle == null || !Handles.TryGetValue(handle, out found) || found == null)
                throw new ArgumentException("Unknown or stale UI handle. Inspect the current hierarchy again.");
            return found;
        }

        private static JObject Describe(GameObject go)
        {
            var item = new JObject { ["handle"] = Remember(go), ["name"] = go.name,
                                     ["active"] = go.activeInHierarchy, ["instanceId"] = go.GetInstanceID() };
            var selectable = go.GetComponent<Selectable>();
            if (selectable != null) item["interactable"] = selectable.IsInteractable();
            var label = go.GetComponent<Text>();
            if (label != null) item["text"] = label.text;
            var tmp = go.GetComponent<TMPro.TMP_Text>();
            if (tmp != null) item["text"] = tmp.text;
            var components = new JArray();
            foreach (var component in go.GetComponents<Component>())
                components.Add(component == null ? "<missing>" : component.GetType().FullName);
            item["components"] = components;
            item["children"] = go.transform.childCount;
            return item;
        }

        internal static JObject Execute(JObject request)
        {
            string op = (string)request["op"];
            if (op == "fixture") return Fixture((string)request["action"] ?? "status");
            if (op == "roots")
            {
                var roots = new JArray();
                for (int i = 0; i < SceneManager.sceneCount && roots.Count < 128; i++)
                {
                    var scene = SceneManager.GetSceneAt(i);
                    if (!scene.isLoaded) continue;
                    foreach (var go in scene.GetRootGameObjects())
                    {
                        if (roots.Count >= 128) break;
                        roots.Add(Describe(go));
                    }
                }
                // Persistent UI is often in DontDestroyOnLoad, absent from sceneCount.
                var canvases = new JArray();
                foreach (var canvas in Resources.FindObjectsOfTypeAll<Canvas>())
                {
                    if (canvases.Count >= 128) break;
                    if (canvas != null && canvas.gameObject.scene.IsValid()) canvases.Add(Describe(canvas.gameObject));
                }
                return new JObject { ["roots"] = roots, ["canvases"] = canvases, ["limit"] = 128 };
            }
            var root = Resolve((string)request["handle"]);
            if (op == "inspect") return new JObject { ["object"] = Describe(root) };
            if (op == "click")
            {
                var selectable = root.GetComponent<Selectable>();
                if (!(selectable is Button) && !(selectable is Toggle))
                    throw new ArgumentException("Click supports Button and Toggle only; inspect other control handlers explicitly.");
                if (!root.activeInHierarchy || !selectable.isActiveAndEnabled || !selectable.IsInteractable())
                    throw new InvalidOperationException("Control is inactive or non-interactable; nothing was invoked.");
                var events = EventSystem.current;
                if (events == null) throw new InvalidOperationException("No EventSystem is active.");
                var rect = root.transform as RectTransform;
                var canvas = root.GetComponentInParent<Canvas>();
                if (rect == null || canvas == null) throw new InvalidOperationException("Control is not in a UI canvas.");
                Camera camera = canvas.renderMode == RenderMode.ScreenSpaceOverlay ? null : canvas.worldCamera;
                var position = RectTransformUtility.WorldToScreenPoint(camera, rect.TransformPoint(rect.rect.center));
                var pointer = new PointerEventData(events) { button = PointerEventData.InputButton.Left, position = position };
                var hits = new List<RaycastResult>();
                events.RaycastAll(pointer, hits);
                if (hits.Count == 0 || !(hits[0].gameObject == root || hits[0].gameObject.transform.IsChildOf(root.transform)))
                    throw new InvalidOperationException("Control center is not the top raycast hit (hidden or occluded); nothing was invoked.");
                bool invoked = ExecuteEvents.Execute(root, pointer, ExecuteEvents.pointerClickHandler);
                return new JObject { ["invoked"] = invoked, ["evidence"] = "Unity event handler with center raycast; not an OS pointer click",
                                     ["fixtureClicks"] = clicks };
            }
            if (op == "tree")
            {
                int limit = Math.Max(1, Math.Min(200, (int?)request["limit"] ?? 100));
                int depth = Math.Max(0, Math.Min(8, (int?)request["depth"] ?? 3));
                var queue = new Queue<KeyValuePair<Transform, int>>();
                queue.Enqueue(new KeyValuePair<Transform, int>(root.transform, 0));
                var items = new JArray();
                while (queue.Count > 0 && items.Count < limit)
                {
                    var current = queue.Dequeue();
                    var item = Describe(current.Key.gameObject);
                    item["depth"] = current.Value;
                    items.Add(item);
                    if (current.Value >= depth) continue;
                    for (int i = 0; i < current.Key.childCount && queue.Count + items.Count < limit; i++)
                        queue.Enqueue(new KeyValuePair<Transform, int>(current.Key.GetChild(i), current.Value + 1));
                }
                return new JObject { ["objects"] = items, ["limit"] = limit, ["depthLimit"] = depth,
                                     ["bounded"] = true };
            }
            throw new ArgumentException("Unknown UI operation");
        }

        private static JObject Fixture(string action)
        {
            if (action == "destroy")
            {
                if (fixture != null) UnityEngine.Object.Destroy(fixture);
                fixture = null;
                return new JObject { ["exists"] = false };
            }
            if (action == "create")
            {
                if (fixture != null) UnityEngine.Object.Destroy(fixture);
                fixture = new GameObject("TiModTemplateTestCanvas", typeof(RectTransform), typeof(Canvas), typeof(GraphicRaycaster));
                var canvas = fixture.GetComponent<Canvas>();
                canvas.renderMode = RenderMode.ScreenSpaceOverlay;
                canvas.sortingOrder = 30000;
                clicks = 0;
                Button enabled = MakeButton("EnabledTestButton", new Vector2(150, 80), true);
                Button disabled = MakeButton("DisabledTestButton", new Vector2(150, 130), false);
                return new JObject { ["root"] = Describe(fixture), ["button"] = Describe(enabled.gameObject),
                                     ["disabledButton"] = Describe(disabled.gameObject), ["clicks"] = clicks };
            }
            if (action != "status") throw new ArgumentException("Fixture action must be create, destroy, or status.");
            return new JObject { ["exists"] = fixture != null, ["clicks"] = clicks };
        }

        private static Button MakeButton(string name, Vector2 position, bool interactable)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(Button));
            go.transform.SetParent(fixture.transform, false);
            var rect = go.GetComponent<RectTransform>();
            rect.anchorMin = rect.anchorMax = Vector2.zero;
            rect.sizeDelta = new Vector2(250, 40);
            rect.anchoredPosition = position;
            var image = go.GetComponent<Image>();
            image.color = new Color(0.12f, 0.25f, 0.4f, 1f);
            var button = go.GetComponent<Button>();
            button.targetGraphic = image;
            button.interactable = interactable;
            button.onClick.AddListener(delegate { clicks++; });
            var textGo = new GameObject("Label", typeof(RectTransform), typeof(Text));
            textGo.transform.SetParent(go.transform, false);
            var textRect = textGo.GetComponent<RectTransform>();
            textRect.anchorMin = Vector2.zero;
            textRect.anchorMax = Vector2.one;
            textRect.offsetMin = textRect.offsetMax = Vector2.zero;
            var text = textGo.GetComponent<Text>();
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.fontSize = 16;
            text.alignment = TextAnchor.MiddleCenter;
            text.text = interactable ? "Template test: enabled" : "Template test: disabled";
            text.raycastTarget = false;
            return button;
        }
    }
}
