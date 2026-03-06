import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mic, BarChart3, Sparkles, UtensilsCrossed, PhoneCall, LayoutDashboard } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// --- SHADCN COMPONENTS (Simulated via Tailwind) ---

const Button = ({ className, variant = "default", ...props }) => {
  const base = "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-9 px-4 py-2";
  const variants = {
    default: "bg-white text-black hover:bg-white/90 shadow",
    destructive: "bg-red-500 text-white shadow-sm hover:bg-red-500/90",
    outline: "border border-white/20 bg-transparent shadow-sm hover:bg-white/10 text-white",
    ghost: "hover:bg-white/10 text-white",
  };
  return <button className={cn(base, variants[variant], className)} {...props} />;
};

const Card = ({ className, ...props }) => (
  <div className={cn("rounded-xl border border-white/10 bg-black/50 backdrop-blur-sm text-white shadow", className)} {...props} />
);

const CardHeader = ({ className, ...props }) => (
  <div className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
);

const CardTitle = ({ className, ...props }) => (
  <div className={cn("font-semibold leading-none tracking-tight", className)} {...props} />
);

const CardContent = ({ className, ...props }) => (
  <div className={cn("p-6 pt-0 text-gray-400 text-sm", className)} {...props} />
);

const Badge = ({ className, ...props }) => (
  <div className={cn("inline-flex items-center rounded-md border border-white/10 px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 text-white bg-white/5", className)} {...props} />
);

const Separator = ({ className, ...props }) => (
  <div className={cn("shrink-0 bg-white/10 h-[1px] w-full", className)} {...props} />
);

// --- FRAME LOADING ---

const frameModules = import.meta.glob("../assets/frames/*.jpg", { eager: true });
const frames = Object.entries(frameModules)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([, module]) => module.default);

export default function Landing() {
  const navigate = useNavigate();
  const sectionRef = useRef(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [isLoaded, setIsLoaded] = useState(false);

  // Preload frames
  useEffect(() => {
    let loadedCount = 0;
    const totalFrames = frames.length;

    if (totalFrames === 0) {
      setIsLoaded(true);
      return;
    }

    const preloadedImages = frames.map((src) => {
      const img = new Image();
      img.src = src;
      img.onload = () => {
        loadedCount++;
        if (loadedCount === totalFrames) {
          setIsLoaded(true);
        }
      };
      img.onerror = () => {
        loadedCount++;
        if (loadedCount === totalFrames) {
          setIsLoaded(true);
        }
      };
      return img;
    });
  }, []);

  // Scroll logic
  useEffect(() => {
    if (!isLoaded || frames.length === 0) return;

    let rafId = null;
    const totalFrames = frames.length;

    const handleScroll = () => {
      if (rafId) return;

      rafId = requestAnimationFrame(() => {
        rafId = null;
        if (!sectionRef.current) return;

        const rect = sectionRef.current.getBoundingClientRect();
        const sectionHeight = sectionRef.current.offsetHeight;

        const scrollInside = Math.min(
          Math.max(-rect.top, 0),
          sectionHeight
        );

        // Calculate progress ensuring bounds between 0 and 1
        const progress = Math.max(0, Math.min(scrollInside / sectionHeight, 1));

        // Use Math.round to prevent frame skipping
        const index = Math.round(progress * (totalFrames - 1));

        setFrameIndex(index);
      });
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll(); // initial call to set right frame

    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [isLoaded]);

  return (
    <div className="min-h-screen bg-black text-white selection:bg-red-500/30 font-sans flex flex-col">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 border-b border-white/10 bg-black/50 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
            <UtensilsCrossed className="w-6 h-6 text-red-500" />
            <span>AI Restaurant Copilot</span>
          </div>
        </div>
      </nav>

      <main className="flex-1">
        {/* Hero Section */}
        <section ref={sectionRef} className="relative h-[300vh]">
          <div className="sticky top-0 h-screen w-full overflow-hidden flex items-center justify-center bg-black">

            {/* Background Frame rendering using a single Img to avoid flashes */}
            <div className="absolute inset-0 z-0 flex items-center justify-center">
              {isLoaded && frames.length > 0 && (
                <img
                  src={frames[frameIndex]}
                  alt="Hero Animation"
                  className="absolute inset-0 w-full h-full object-contain"
                />
              )}
            </div>

            {/* Dark overlay for readability */}
            <div className="absolute inset-0 bg-black/40 z-10" />

            {/* Text Content */}
            <div className="relative z-20 flex flex-col items-center justify-center h-full text-center px-6 max-w-4xl mx-auto">
              <Badge className="mb-6 px-3 py-1 text-sm border-white/20">
                <Sparkles className="w-4 h-4 mr-2 text-red-500" />
                AI-Powered POS Intelligence
              </Badge>

              <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
                AI Revenue & Voice
                <span className="text-red-500 block mt-2">Copilot for Restaurants</span>
              </h1>

              <p className="text-lg md:text-xl text-gray-300 max-w-2xl mb-10 leading-relaxed">
                Turn POS data into revenue insights and automate phone ordering with AI.
              </p>

              <div className="flex flex-col sm:flex-row gap-4">
                <Button className="h-12 px-8 text-base font-semibold" onClick={() => navigate('/login')}>
                  Login
                </Button>
                <Button variant="destructive" className="h-12 px-8 text-base font-semibold" onClick={() => navigate('/signup')}>
                  Sign Up
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* Feature Section */}
        <section className="py-32 px-6 bg-black relative z-20 border-t border-white/10">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">Supercharge Your Operations</h2>
              <p className="text-gray-400 max-w-2xl mx-auto">Comprehensive toolkit designed to increase restaurant revenue and fully automate your phone lines.</p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              <Card>
                <CardHeader>
                  <div className="w-12 h-12 bg-red-500/10 rounded-lg flex items-center justify-center mb-4 border border-red-500/20">
                    <Mic className="w-6 h-6 text-red-500" />
                  </div>
                  <CardTitle className="text-xl">Voice Ordering</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Speech to text ordering</li>
                    <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Multi-language support</li>
                    <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> AI upsell suggestions</li>
                  </ul>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="w-12 h-12 bg-red-500/10 rounded-lg flex items-center justify-center mb-4 border border-red-500/20">
                    <BarChart3 className="w-6 h-6 text-red-500" />
                  </div>
                  <CardTitle className="text-xl">Revenue Intelligence</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Menu profitability insights</li>
                    <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Sales trends</li>
                  </ul>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="w-12 h-12 bg-red-500/10 rounded-lg flex items-center justify-center mb-4 border border-red-500/20">
                    <LayoutDashboard className="w-6 h-6 text-red-500" />
                  </div>
                  <CardTitle className="text-xl">Smart Recommendations</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Apriori combo detection</li>
                    <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Upsell suggestions</li>
                  </ul>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        {/* How It Works Section */}
        <section className="py-32 px-6 bg-zinc-950 relative z-20 border-t border-white/10">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">How It Works</h2>
              <p className="text-gray-400 max-w-2xl mx-auto">Fully automated order processing from the customer's voice directly to your POS.</p>
            </div>

            <div className="grid md:grid-cols-3 gap-8 relative items-start">
              {/* Connection lines between steps (Desktop) */}
              <div className="hidden md:block absolute top-[48px] left-[16%] right-[16%] h-[2px] bg-gradient-to-r from-red-500/0 via-red-500/50 to-red-500/0" />

              <div className="flex flex-col items-center text-center relative z-10">
                <div className="w-24 h-24 rounded-full bg-black border border-white/10 flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(239,68,68,0.15)] relative">
                  <span className="text-lg font-bold text-gray-500 absolute -top-1 -right-1 bg-black rounded-full w-8 h-8 flex items-center justify-center border border-white/10">1</span>
                  <PhoneCall className="w-10 h-10 text-red-400" />
                </div>
                <h3 className="text-xl font-bold mb-3">Customer calls</h3>
                <p className="text-gray-400">Customer calls restaurant to place an order over the phone.</p>
              </div>

              <div className="flex flex-col items-center text-center relative z-10">
                <div className="w-24 h-24 rounded-full bg-black border border-white/10 flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(239,68,68,0.15)] relative">
                  <span className="text-lg font-bold text-gray-500 absolute -top-1 -right-1 bg-black rounded-full w-8 h-8 flex items-center justify-center border border-white/10">2</span>
                  <Sparkles className="w-10 h-10 text-red-500" />
                </div>
                <h3 className="text-xl font-bold mb-3">AI Processes</h3>
                <p className="text-gray-400">AI order-taker handles the call naturally, answers menu questions, and upsells.</p>
              </div>

              <div className="flex flex-col items-center text-center relative z-10">
                <div className="w-24 h-24 rounded-full bg-black border border-white/10 flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(239,68,68,0.15)] relative">
                  <span className="text-lg font-bold text-gray-500 absolute -top-1 -right-1 bg-black rounded-full w-8 h-8 flex items-center justify-center border border-white/10">3</span>
                  <LayoutDashboard className="w-10 h-10 text-red-400" />
                </div>
                <h3 className="text-xl font-bold mb-3">Order appears</h3>
                <p className="text-gray-400">Order appears instantly in POS dashboard, ready for the kitchen.</p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-black border-t border-white/10 pt-16 pb-8 px-6 relative z-20">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-16">
            <div className="col-span-2 md:col-span-2">
              <div className="flex items-center gap-2 font-bold text-xl tracking-tight mb-4">
                <UtensilsCrossed className="w-6 h-6 text-red-500" />
                <span>AI Restaurant Copilot</span>
              </div>
              <p className="text-gray-400 max-w-sm">
                Empowering restaurant owners with next-generation AI agents to take calls and maximize margins.
              </p>
            </div>

            <div>
              <h4 className="font-semibold mb-4 text-white">Product</h4>
              <ul className="space-y-3 text-gray-400 text-sm">
                <li><a href="#" className="hover:text-red-400 transition-colors">Voice Ordering</a></li>
                <li><a href="#" className="hover:text-red-400 transition-colors">Dashboard</a></li>
                <li><a href="#" className="hover:text-red-400 transition-colors">Analytics</a></li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold mb-4 text-white">Company</h4>
              <ul className="space-y-3 text-gray-400 text-sm">
                <li><a href="#" className="hover:text-red-400 transition-colors">About</a></li>
                <li><a href="#" className="hover:text-red-400 transition-colors">GitHub</a></li>
                <li><a href="#" className="hover:text-red-400 transition-colors">Contact</a></li>
              </ul>
            </div>
          </div>

          <Separator className="mb-8" />

          <div className="text-center text-gray-500 text-sm">
            <p>© 2026 AI Restaurant Copilot</p>
          </div>
        </div>
      </footer>
    </div>
  );
}