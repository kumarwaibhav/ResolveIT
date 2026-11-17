import spec from "../../openapi.json";

/** Reads the real OpenAPI contract so the reference can never drift from the API. */
type Schema = {
  $ref?: string;
  type?: string;
  enum?: unknown[];
  items?: Schema;
  anyOf?: Schema[];
  properties?: Record<string, Schema>;
  required?: string[];
  default?: unknown;
  maxLength?: number;
  minLength?: number;
  minimum?: number;
  maximum?: number;
  additionalProperties?: boolean | Schema;
  title?: string;
  description?: string;
};

const schemas = (spec as unknown as { components: { schemas: Record<string, Schema> } }).components.schemas;

export function resolve(s: Schema | undefined): Schema {
  let cur = s ?? {};
  for (let i = 0; cur.$ref && i < 10; i++) cur = schemas[cur.$ref.split("/").pop()!] ?? {};
  return cur;
}

export function typeName(s: Schema | undefined): string {
  if (!s) return "any";
  if (s.$ref) {
    const name = s.$ref.split("/").pop()!;
    const r = resolve(s);
    return r.enum ? `${name} (enum)` : name;
  }
  if (s.anyOf) return s.anyOf.map(typeName).join(" | ");
  if (s.enum) return s.enum.map((v) => JSON.stringify(v)).join(" | ");
  if (s.type === "array") return `${typeName(s.items)}[]`;
  if (s.type === "object" && s.additionalProperties && typeof s.additionalProperties === "object") return `map<string, ${typeName(s.additionalProperties)}>`;
  return s.type ?? "object";
}

export interface Field {
  name: string;
  type: string;
  required: boolean;
  note: string;
}

export function fields(s: Schema | undefined): Field[] {
  const r = resolve(s);
  return Object.entries(r.properties ?? {}).map(([name, p]) => {
    const notes: string[] = [];
    if (p.default !== undefined) notes.push(`default ${JSON.stringify(p.default)}`);
    if (p.minLength !== undefined || p.maxLength !== undefined) notes.push(`${p.minLength ?? 0}–${p.maxLength ?? "∞"} chars`);
    if (p.minimum !== undefined || p.maximum !== undefined) notes.push(`${p.minimum ?? "−∞"}…${p.maximum ?? "∞"}`);
    const rp = resolve(p);
    if (p.$ref && rp.enum) notes.push(`one of ${rp.enum.map(String).join(", ")}`);
    return { name, type: typeName(p), required: (r.required ?? []).includes(name), note: notes.join(" · ") };
  });
}

export interface Operation {
  method: string;
  path: string;
  summary: string;
  params: { name: string; in: string; required: boolean; type: string }[];
  body: Field[];
  bodyName: string | null;
  response: Field[];
  responseName: string | null;
  codes: string[];
}

type RawOp = {
  summary?: string;
  parameters?: { name: string; in: string; required?: boolean; schema?: Schema }[];
  requestBody?: { content?: { "application/json"?: { schema?: Schema } } };
  responses?: Record<string, { content?: { "application/json"?: { schema?: Schema } } }>;
};

export function operations(): Operation[] {
  const paths = (spec as unknown as { paths: Record<string, Record<string, RawOp>> }).paths;
  const out: Operation[] = [];
  for (const [path, ops] of Object.entries(paths)) {
    for (const [method, op] of Object.entries(ops)) {
      const bodySchema = op.requestBody?.content?.["application/json"]?.schema;
      const ok = Object.entries(op.responses ?? {}).find(([c]) => c.startsWith("2"));
      const resSchema = ok?.[1].content?.["application/json"]?.schema;
      out.push({
        method: method.toUpperCase(),
        path,
        summary: op.summary ?? "",
        params: (op.parameters ?? [])
          .filter((p) => p.name !== "authorization" && !p.name.startsWith("mcp-"))
          .map((p) => ({ name: p.name, in: p.in, required: !!p.required, type: typeName(p.schema) })),
        body: fields(bodySchema),
        bodyName: bodySchema?.$ref?.split("/").pop() ?? null,
        response: fields(resSchema),
        responseName: resSchema?.$ref?.split("/").pop() ?? null,
        codes: Object.keys(op.responses ?? {}),
      });
    }
  }
  return out;
}

export function enumValues(name: string): string[] {
  return (schemas[name]?.enum ?? []).map(String);
}
