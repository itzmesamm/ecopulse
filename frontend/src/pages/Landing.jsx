import Navbar from "../components/landing/Navbar";
import Hero from "../components/landing/Hero";
import LogoStrip from "../components/landing/LogoStrip";
import BentoFeatures from "../components/landing/BentoFeatures";
import SecurityBand from "../components/landing/SecurityBand";
import { FinalCTA, Footer } from "../components/landing/FinalCTA";

export default function Landing() {
  return (
    <div>
      <Navbar />
      <Hero />
      <LogoStrip />
      <BentoFeatures />
      <div style={{ padding: "0 56px" }}>
        <SecurityBand />
      </div>
      <FinalCTA />
      <Footer />
    </div>
  );
}
