import commonjs from "@rollup/plugin-commonjs";
import resolve from "@rollup/plugin-node-resolve";

export default {
  input: "src/plugin.js",
  output: { file: "com.wizardmelon.dm-backup.sdPlugin/bin/plugin.js", format: "esm", sourcemap: false },
  external: [/^node:/],
  plugins: [resolve({ preferBuiltins: true, exportConditions: ["node"] }), commonjs()],
};
