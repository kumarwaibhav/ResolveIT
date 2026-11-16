import { expect, it } from "vitest";
import { boundedBody } from "@/lib/bounded-body";

it("enforces streamed bytes when content length lies", async () => {
  const body = new ReadableStream({ start(controller) {
    controller.enqueue(new TextEncoder().encode("123"));
    controller.enqueue(new TextEncoder().encode("456"));
    controller.close();
  } });
  const request = new Request("http://localhost", { method: "POST", body, headers: { "content-length": "1" }, duplex: "half" } as RequestInit);
  const response = await boundedBody(request, 5);
  expect(response).toBeInstanceOf(Response);
  expect((response as Response).status).toBe(413);
});
it("accepts exact byte boundary and rejects invalid UTF-8", async () => {
  expect(await boundedBody(new Request("http://localhost", { method: "POST", body: "abc" }), 3)).toBe("abc");
  const response = await boundedBody(new Request("http://localhost", { method: "POST", body: new Uint8Array([255]) }));
  expect((response as Response).status).toBe(400);
});
