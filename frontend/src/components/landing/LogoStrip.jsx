const LOGOS = ["Northwind", "Alto Systems", "Fernbank", "Ridgeline", "Cobalt Labs", "Marrow"];

export default function LogoStrip() {
  return (
    <section className="logo-strip">
      <div className="lbl">Trusted by platform teams shipping on AWS, GCP &amp; Azure</div>
      <div className="row">
        {LOGOS.map((l) => (
          <span key={l}>{l}</span>
        ))}
      </div>
    </section>
  );
}
