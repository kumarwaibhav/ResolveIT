import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md space-y-3 py-16 text-center">
      <h1 className="text-xl font-semibold">Nothing here</h1>
      <p className="text-sm text-muted-foreground">That page or incident does not exist, or belongs to another workspace.</p>
      <Link href="/" className="text-sm text-signal underline underline-offset-4">Report a problem</Link>
    </div>
  );
}
