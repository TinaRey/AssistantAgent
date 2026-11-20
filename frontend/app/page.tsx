import { StatusBadge } from "@/components/StatusBadge";

export default function Home() {
  return (
    <main className="container">
      <h1>Pantalelle Assistant</h1>
      <p>Your private assistant for prospecting and marketing content.</p>
      <StatusBadge />
    </main>
  );
}
