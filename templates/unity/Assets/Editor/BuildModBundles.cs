using System.IO;
using UnityEditor;

public static class BuildModBundles
{
    [MenuItem("TI Mod/Build Windows bundles")]
    public static void Build()
    {
        if (UnityEngine.Application.unityVersion != "2020.3.49f1")
            throw new System.InvalidOperationException("This authoring profile requires Unity 2020.3.49f1. Verify another game/editor combination before changing it.");
        if (AssetDatabase.GetAllAssetBundleNames().Length == 0)
            throw new System.InvalidOperationException("Assign at least one asset to a bundle before building.");
        string projectRoot = Directory.GetParent(UnityEngine.Application.dataPath).FullName;
        string output = Path.GetFullPath(Path.Combine(projectRoot, "../../.local/asset-bundles"));
        Directory.CreateDirectory(output);
        var manifest = BuildPipeline.BuildAssetBundles(output, BuildAssetBundleOptions.StrictMode, BuildTarget.StandaloneWindows64);
        if (manifest == null) throw new System.InvalidOperationException("Bundle build failed; inspect the Unity log.");
        UnityEngine.Debug.Log("TI bundles written to " + output);
    }
}
