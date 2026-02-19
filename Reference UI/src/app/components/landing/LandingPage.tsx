import { useState } from "react";
import { useNavigate } from "react-router";
import {
  Shield, TrendingUp, Home, CreditCard, Phone, Mail, MapPin,
  ChevronRight, Users, Clock, Award, ArrowRight, Menu, X
} from "lucide-react";
import { ImageWithFallback } from "../figma/ImageWithFallback";
import { ChatWidget } from "../chatbot/ChatWidget";

export function LandingPage() {
  const navigate = useNavigate();
  const [mobileMenu, setMobileMenu] = useState(false);

  return (
    <div className="min-h-screen bg-white">
      {/* Navbar */}
      <nav className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--brand-gradient)" }}>
                <Shield className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl" style={{ fontWeight: 700 }}>HFCL Finance</span>
            </div>

            <div className="hidden md:flex items-center gap-8">
              <a href="#products" className="text-gray-600 hover:text-gray-900 transition-colors">Products</a>
              <a href="#about" className="text-gray-600 hover:text-gray-900 transition-colors">About</a>
              <a href="#services" className="text-gray-600 hover:text-gray-900 transition-colors">Services</a>
              <a href="#contact" className="text-gray-600 hover:text-gray-900 transition-colors">Contact</a>
              <button
                onClick={() => navigate("/admin")}
                className="px-4 py-2 rounded-lg text-white transition-all hover:opacity-90"
                style={{ background: "var(--brand-gradient)" }}
              >
                Admin Console
              </button>
            </div>

            <button className="md:hidden" onClick={() => setMobileMenu(!mobileMenu)}>
              {mobileMenu ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {mobileMenu && (
          <div className="md:hidden border-t border-gray-100 bg-white px-4 pb-4">
            <a href="#products" className="block py-2 text-gray-600">Products</a>
            <a href="#about" className="block py-2 text-gray-600">About</a>
            <a href="#services" className="block py-2 text-gray-600">Services</a>
            <a href="#contact" className="block py-2 text-gray-600">Contact</a>
            <button
              onClick={() => navigate("/admin")}
              className="mt-2 w-full px-4 py-2 rounded-lg text-white"
              style={{ background: "var(--brand-gradient)" }}
            >
              Admin Console
            </button>
          </div>
        )}
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 opacity-5" style={{ background: "var(--brand-gradient)" }} />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-28">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-light/20 text-brand-dark mb-6" style={{ fontSize: 14 }}>
                <Award className="w-4 h-4" /> RBI Registered NBFC
              </div>
              <h1 className="text-4xl lg:text-5xl tracking-tight text-gray-900 mb-6" style={{ fontWeight: 700, lineHeight: 1.15 }}>
                Your Trusted Partner for{" "}
                <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--brand-gradient)" }}>
                  Financial Growth
                </span>
              </h1>
              <p className="text-lg text-gray-600 mb-8 max-w-lg">
                HFCL Finance offers competitive home loans, personal loans, and property financing
                solutions tailored to your needs. Experience seamless digital lending.
              </p>
              <div className="flex flex-wrap gap-4">
                <button
                  className="px-6 py-3 rounded-xl text-white flex items-center gap-2 hover:opacity-90 transition-all shadow-lg"
                  style={{ background: "var(--brand-gradient)" }}
                >
                  Apply Now <ArrowRight className="w-4 h-4" />
                </button>
                <button className="px-6 py-3 rounded-xl border-2 border-brand-main text-brand-dark hover:bg-brand-light/10 transition-all flex items-center gap-2">
                  Check Eligibility <ChevronRight className="w-4 h-4" />
                </button>
              </div>

              <div className="flex gap-8 mt-12">
                <div>
                  <div className="text-2xl text-gray-900" style={{ fontWeight: 700 }}>25+</div>
                  <div className="text-sm text-gray-500">Years Experience</div>
                </div>
                <div>
                  <div className="text-2xl text-gray-900" style={{ fontWeight: 700 }}>5L+</div>
                  <div className="text-sm text-gray-500">Happy Customers</div>
                </div>
                <div>
                  <div className="text-2xl text-gray-900" style={{ fontWeight: 700 }}>₹50K Cr</div>
                  <div className="text-sm text-gray-500">Assets Under Mgmt</div>
                </div>
              </div>
            </div>

            <div className="relative hidden lg:block">
              <div className="absolute -inset-4 rounded-3xl opacity-20 blur-2xl" style={{ background: "var(--brand-gradient)" }} />
              <ImageWithFallback
                src="https://images.unsplash.com/photo-1760124056883-732e7a5e2e68?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBvZmZpY2UlMjBidWlsZGluZyUyMGZpbmFuY2UlMjBjb3Jwb3JhdGV8ZW58MXx8fHwxNzcxNDcwMjE2fDA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                alt="HFCL Finance Office"
                className="relative rounded-2xl shadow-2xl w-full object-cover"
                style={{ height: 420 }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* Products Section */}
      <section id="products" className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-3xl text-gray-900 mb-4" style={{ fontWeight: 700 }}>Our Financial Products</h2>
            <p className="text-gray-600 max-w-2xl mx-auto">Comprehensive lending solutions designed for every milestone in your life</p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { icon: Home, title: "Home Loans", rate: "8.5%", desc: "Affordable home financing with flexible EMIs up to 30 years" },
              { icon: CreditCard, title: "Personal Loans", rate: "10.5%", desc: "Quick personal loans with minimal documentation" },
              { icon: TrendingUp, title: "Loan Against Property", rate: "9.0%", desc: "Unlock your property value with attractive rates" },
              { icon: Shield, title: "Business Loans", rate: "11.0%", desc: "Fuel your business growth with easy capital access" },
            ].map((product) => (
              <div key={product.title} className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-lg transition-all border border-gray-100 group cursor-pointer">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform"
                  style={{ background: "var(--brand-gradient)" }}
                >
                  <product.icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-gray-900 mb-1" style={{ fontWeight: 600 }}>{product.title}</h3>
                <div className="text-brand-dark mb-3" style={{ fontWeight: 700, fontSize: 14 }}>Starting from {product.rate} p.a.</div>
                <p className="text-sm text-gray-500">{product.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* About Section */}
      <section id="about" className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div className="relative">
              <ImageWithFallback
                src="https://images.unsplash.com/photo-1565688527174-775059ac429c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxidXNpbmVzcyUyMG1lZXRpbmclMjBmaW5hbmNpYWwlMjBhZHZpc29yfGVufDF8fHx8MTc3MTQ3MDIxN3ww&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                alt="Financial Advisory"
                className="rounded-2xl shadow-xl w-full object-cover"
                style={{ height: 380 }}
              />
            </div>
            <div>
              <h2 className="text-3xl text-gray-900 mb-6" style={{ fontWeight: 700 }}>Trusted by Millions Across India</h2>
              <p className="text-gray-600 mb-8">
                HFCL Finance has been a cornerstone of India's lending ecosystem for over 25 years.
                Our AI-powered customer service ensures you get instant answers to all your queries, 24/7.
              </p>
              <div className="space-y-4">
                {[
                  { icon: Users, text: "5 Lakh+ satisfied customers across 200+ cities" },
                  { icon: Clock, text: "24/7 AI-powered customer support" },
                  { icon: Shield, text: "RBI registered & fully compliant" },
                  { icon: Award, text: "Award-winning digital lending platform" },
                ].map((item) => (
                  <div key={item.text} className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-brand-light/20">
                      <item.icon className="w-4 h-4 text-brand-dark" />
                    </div>
                    <span className="text-gray-700">{item.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Services Section */}
      <section id="services" className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-3xl text-gray-900 mb-4" style={{ fontWeight: 700 }}>Why Choose HFCL?</h2>
          </div>
          <div className="grid sm:grid-cols-3 gap-8">
            {[
              { title: "Quick Disbursement", desc: "Get your loan approved and disbursed within 48 hours with our fast-track processing.", stat: "48hrs" },
              { title: "Lowest Interest Rates", desc: "We offer some of the most competitive rates in the market, saving you lakhs.", stat: "8.5%" },
              { title: "100% Digital Process", desc: "Apply, track, and manage your loans entirely online. No branch visits needed.", stat: "100%" },
            ].map((service) => (
              <div key={service.title} className="text-center p-8 bg-white rounded-2xl shadow-sm border border-gray-100">
                <div
                  className="text-4xl mb-4 bg-clip-text text-transparent inline-block"
                  style={{ backgroundImage: "var(--brand-gradient)", fontWeight: 800 }}
                >
                  {service.stat}
                </div>
                <h3 className="text-gray-900 mb-2" style={{ fontWeight: 600 }}>{service.title}</h3>
                <p className="text-sm text-gray-500">{service.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="rounded-3xl p-12 text-center text-white relative overflow-hidden" style={{ background: "var(--brand-gradient)" }}>
            <div className="absolute inset-0 bg-black/10" />
            <div className="relative">
              <h2 className="text-3xl mb-4" style={{ fontWeight: 700 }}>Ready to Get Started?</h2>
              <p className="text-white/90 mb-8 max-w-xl mx-auto">
                Apply for a loan today and get pre-approved within minutes. Our AI assistant is available 24/7 to help!
              </p>
              <div className="flex flex-wrap justify-center gap-4">
                <button className="px-8 py-3 bg-white text-brand-dark rounded-xl hover:bg-white/90 transition-all" style={{ fontWeight: 600 }}>
                  Apply for Loan
                </button>
                <button className="px-8 py-3 border-2 border-white text-white rounded-xl hover:bg-white/10 transition-all">
                  Talk to Advisor
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section id="contact" className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-3xl text-gray-900 mb-4" style={{ fontWeight: 700 }}>Get In Touch</h2>
          </div>
          <div className="grid sm:grid-cols-3 gap-8">
            {[
              { icon: Phone, title: "Call Us", info: "1800-XXX-XXXX", sub: "Toll-free, 24/7" },
              { icon: Mail, title: "Email Us", info: "support@hfcl.finance", sub: "We reply within 2 hours" },
              { icon: MapPin, title: "Visit Us", info: "Mumbai, Maharashtra", sub: "200+ branches nationwide" },
            ].map((contact) => (
              <div key={contact.title} className="text-center p-6">
                <div className="w-12 h-12 rounded-xl mx-auto flex items-center justify-center mb-4" style={{ background: "var(--brand-gradient)" }}>
                  <contact.icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-gray-900 mb-1" style={{ fontWeight: 600 }}>{contact.title}</h3>
                <p className="text-brand-dark" style={{ fontWeight: 500 }}>{contact.info}</p>
                <p className="text-sm text-gray-500">{contact.sub}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid sm:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--brand-gradient)" }}>
                  <Shield className="w-5 h-5 text-white" />
                </div>
                <span style={{ fontWeight: 700 }}>HFCL Finance</span>
              </div>
              <p className="text-gray-400 text-sm">Your trusted NBFC partner for all financial needs since 2001.</p>
            </div>
            <div>
              <h4 className="mb-3" style={{ fontWeight: 600 }}>Products</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><a href="#" className="hover:text-white">Home Loans</a></li>
                <li><a href="#" className="hover:text-white">Personal Loans</a></li>
                <li><a href="#" className="hover:text-white">Business Loans</a></li>
                <li><a href="#" className="hover:text-white">Loan Against Property</a></li>
              </ul>
            </div>
            <div>
              <h4 className="mb-3" style={{ fontWeight: 600 }}>Company</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><a href="#" className="hover:text-white">About Us</a></li>
                <li><a href="#" className="hover:text-white">Careers</a></li>
                <li><a href="#" className="hover:text-white">Press</a></li>
                <li><a href="#" className="hover:text-white">Investor Relations</a></li>
              </ul>
            </div>
            <div>
              <h4 className="mb-3" style={{ fontWeight: 600 }}>Legal</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><a href="#" className="hover:text-white">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-white">Terms of Service</a></li>
                <li><a href="#" className="hover:text-white">Fair Practices Code</a></li>
                <li><a href="#" className="hover:text-white">Grievance Redressal</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-10 pt-8 text-center text-sm text-gray-500">
            <p>&copy; 2026 HFCL Finance Ltd. All rights reserved. RBI Reg No: N-XX.XXXXX</p>
          </div>
        </div>
      </footer>

      {/* Chat Widget */}
      <ChatWidget />
    </div>
  );
}
