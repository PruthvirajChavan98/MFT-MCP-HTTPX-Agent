import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, ThumbsUp, ThumbsDown, Bot, User, ChevronDown, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  followUps?: string[];
  feedback?: "up" | "down" | null;
}

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  content: "Hello! I'm HFCL's AI assistant. I can help you with information about our loans, EMIs, charges, and more. How can I assist you today?",
  timestamp: new Date(),
  followUps: [
    "What are your home loan interest rates?",
    "How can I check my loan balance?",
    "What documents do I need for a personal loan?",
  ],
};

// Simulated bot responses
const BOT_RESPONSES: Record<string, { answer: string; followUps: string[] }> = {
  default: {
    answer: "Thank you for your question. Our team is here to help you with all your financial needs. Could you please provide more details so I can assist you better?",
    followUps: ["Tell me about home loans", "What are your interest rates?", "How do I apply?"],
  },
  "interest rate": {
    answer: "Our home loan interest rates start from **8.5% p.a.** and vary based on:\n\n- Loan amount\n- Tenure (up to 30 years)\n- Your credit profile (CIBIL score)\n- Property type\n\nFor personal loans, rates start from 10.5% p.a. Would you like to check your eligibility?",
    followUps: ["How is the rate calculated?", "Can I get a lower rate?", "What's the maximum tenure?"],
  },
  "loan balance": {
    answer: "You can check your loan balance through multiple channels:\n\n1. **Mobile App** - Download HFCL Finance app\n2. **Net Banking** - Login at portal.hfcl.finance\n3. **SMS** - Send BAL <Loan A/C No> to 56789\n4. **Branch Visit** - Visit your nearest HFCL branch\n\nNeed help with anything else?",
    followUps: ["How do I download the app?", "Where's the nearest branch?", "How do I register for net banking?"],
  },
  document: {
    answer: "For a **Personal Loan**, you'll need:\n\n- **ID Proof**: Aadhaar Card / PAN Card\n- **Address Proof**: Utility bill / Rental agreement\n- **Income Proof**: Last 3 months salary slips\n- **Bank Statements**: Last 6 months\n- **Photographs**: 2 passport-size photos\n\nFor salaried individuals, the process is even simpler with our digital verification!",
    followUps: ["Can I upload documents online?", "What about self-employed applicants?", "How long does approval take?"],
  },
  foreclosure: {
    answer: "**Foreclosure Charges:**\n\n- **Fixed-rate loans**: 2% of outstanding principal\n- **Floating-rate loans**: **Zero charges** for individual borrowers (as per RBI guidelines)\n\nYou can foreclose your loan anytime through the app or by visiting a branch. Part-prepayment is also available with no charges for floating rate loans.",
    followUps: ["How do I foreclose my loan?", "Can I do part-prepayment?", "Will it affect my credit score?"],
  },
  emi: {
    answer: "**EMI (Equated Monthly Installment)** is the fixed amount you pay every month towards your loan. It includes both principal and interest components.\n\nYou can use our EMI calculator on the website to estimate your monthly payments. For a ₹50 lakh home loan at 8.5% for 20 years, your EMI would be approximately ₹43,391.",
    followUps: ["How is EMI calculated?", "Can I change my EMI date?", "What if I miss an EMI?"],
  },
};

function getResponse(question: string): { answer: string; followUps: string[] } {
  const q = question.toLowerCase();
  if (q.includes("interest") || q.includes("rate")) return BOT_RESPONSES["interest rate"];
  if (q.includes("balance") || q.includes("check")) return BOT_RESPONSES["loan balance"];
  if (q.includes("document") || q.includes("required") || q.includes("need")) return BOT_RESPONSES["document"];
  if (q.includes("foreclosure") || q.includes("close") || q.includes("prepay")) return BOT_RESPONSES["foreclosure"];
  if (q.includes("emi") || q.includes("installment") || q.includes("monthly")) return BOT_RESPONSES["emi"];
  return BOT_RESPONSES["default"];
}

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  const sendMessage = (text: string) => {
    if (!text.trim()) return;

    const userMsg: Message = {
      id: `user_${Date.now()}`,
      role: "user",
      content: text.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    // Simulate streaming response
    setTimeout(() => {
      const response = getResponse(text);
      const botMsg: Message = {
        id: `bot_${Date.now()}`,
        role: "assistant",
        content: response.answer,
        timestamp: new Date(),
        followUps: response.followUps,
        feedback: null,
      };
      setMessages((prev) => [...prev, botMsg]);
      setIsTyping(false);
    }, 1200 + Math.random() * 800);
  };

  const handleFeedback = (messageId: string, type: "up" | "down") => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, feedback: type } : m))
    );
  };

  const formatContent = (content: string) => {
    // Simple markdown-like formatting
    return content.split("\n").map((line, i) => {
      let formatted = line
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>');

      if (line.startsWith("- ")) {
        return (
          <div key={i} className="flex gap-2 ml-2">
            <span className="text-brand-main mt-1">&#8226;</span>
            <span dangerouslySetInnerHTML={{ __html: formatted.slice(2) }} />
          </div>
        );
      }
      if (/^\d+\./.test(line)) {
        return (
          <div key={i} className="ml-2">
            <span dangerouslySetInnerHTML={{ __html: formatted }} />
          </div>
        );
      }
      if (line === "") return <br key={i} />;
      return <p key={i} dangerouslySetInnerHTML={{ __html: formatted }} />;
    });
  };

  return (
    <>
      {/* Chat Bubble */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsOpen(true)}
            className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-xl flex items-center justify-center text-white cursor-pointer"
            style={{ background: "var(--brand-gradient)" }}
          >
            <MessageCircle className="w-6 h-6" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Chat Window */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="fixed bottom-6 right-6 z-50 w-[380px] h-[560px] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden"
            style={{ maxHeight: "calc(100vh - 48px)", maxWidth: "calc(100vw - 32px)" }}
          >
            {/* Header */}
            <div
              className="px-4 py-3 flex items-center justify-between text-white shrink-0"
              style={{ background: "var(--brand-gradient)" }}
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>HFCL Assistant</div>
                  <div className="flex items-center gap-1" style={{ fontSize: 12 }}>
                    <span className="w-2 h-2 rounded-full bg-green-300 inline-block" />
                    Online
                  </div>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="w-8 h-8 rounded-full hover:bg-white/20 flex items-center justify-center transition-colors"
              >
                <ChevronDown className="w-5 h-5" />
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4" style={{ fontSize: 14 }}>
              {messages.map((msg) => (
                <div key={msg.id}>
                  <div className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    {msg.role === "assistant" && (
                      <div
                        className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-1"
                        style={{ background: "var(--brand-gradient)" }}
                      >
                        <Bot className="w-4 h-4 text-white" />
                      </div>
                    )}
                    <div
                      className={`max-w-[280px] px-3 py-2 rounded-2xl ${
                        msg.role === "user"
                          ? "text-white rounded-br-sm"
                          : "bg-gray-100 text-gray-800 rounded-bl-sm"
                      }`}
                      style={msg.role === "user" ? { background: "var(--brand-gradient)" } : {}}
                    >
                      <div className="space-y-1">{formatContent(msg.content)}</div>
                    </div>
                    {msg.role === "user" && (
                      <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center shrink-0 mt-1">
                        <User className="w-4 h-4 text-gray-600" />
                      </div>
                    )}
                  </div>

                  {/* Feedback */}
                  {msg.role === "assistant" && msg.id !== "welcome" && (
                    <div className="flex items-center gap-1 ml-9 mt-1">
                      <button
                        onClick={() => handleFeedback(msg.id, "up")}
                        className={`p-1 rounded hover:bg-gray-100 transition-colors ${
                          msg.feedback === "up" ? "text-green-500" : "text-gray-400"
                        }`}
                      >
                        <ThumbsUp className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => handleFeedback(msg.id, "down")}
                        className={`p-1 rounded hover:bg-gray-100 transition-colors ${
                          msg.feedback === "down" ? "text-red-500" : "text-gray-400"
                        }`}
                      >
                        <ThumbsDown className="w-3 h-3" />
                      </button>
                    </div>
                  )}

                  {/* Follow-up Suggestions */}
                  {msg.followUps && msg.followUps.length > 0 && (
                    <div className="ml-9 mt-2 space-y-1.5">
                      {msg.followUps.map((fu) => (
                        <button
                          key={fu}
                          onClick={() => sendMessage(fu)}
                          className="block w-full text-left px-3 py-1.5 rounded-lg border border-brand-light/50 text-brand-dark hover:bg-brand-light/10 transition-colors"
                          style={{ fontSize: 12 }}
                        >
                          <Sparkles className="w-3 h-3 inline mr-1.5 text-brand-main" />
                          {fu}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {isTyping && (
                <div className="flex gap-2">
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
                    style={{ background: "var(--brand-gradient)" }}
                  >
                    <Bot className="w-4 h-4 text-white" />
                  </div>
                  <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
                    <div className="flex gap-1.5">
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="px-3 pb-3 pt-2 border-t border-gray-100 shrink-0">
              <div className="flex items-center gap-2 bg-gray-50 rounded-xl px-3 py-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
                  placeholder="Ask about loans, EMIs, charges..."
                  className="flex-1 bg-transparent outline-none text-gray-800 placeholder-gray-400"
                  style={{ fontSize: 14 }}
                  disabled={isTyping}
                />
                <button
                  onClick={() => sendMessage(input)}
                  disabled={!input.trim() || isTyping}
                  className="w-8 h-8 rounded-lg flex items-center justify-center text-white disabled:opacity-50 transition-all"
                  style={{ background: "var(--brand-gradient)" }}
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
              <div className="text-center mt-2 text-gray-400" style={{ fontSize: 10 }}>
                Powered by HFCL AI &middot; Responses may not always be accurate
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
