import { useState } from "react";
import {
  Search, Plus, Trash2, Edit3, Upload, Download, Database,
  ChevronDown, X, FileText, Sparkles, AlertTriangle
} from "lucide-react";
import { mockFAQs } from "../../lib/api";

interface FAQ {
  id: string;
  question: string;
  answer: string;
  category: string;
  created_at: string;
}

export function KnowledgeBase() {
  const [faqs, setFaqs] = useState<FAQ[]>(mockFAQs);
  const [searchQuery, setSearchQuery] = useState("");
  const [semanticSearch, setSemanticSearch] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [editingFaq, setEditingFaq] = useState<FAQ | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [newFaq, setNewFaq] = useState({ question: "", answer: "", category: "General" });
  const [semanticResults, setSemanticResults] = useState<{ question: string; score: number }[]>([]);
  const [showSemanticResults, setShowSemanticResults] = useState(false);

  const categories = ["All", ...Array.from(new Set(faqs.map((f) => f.category)))];

  const filtered = faqs.filter((faq) => {
    const matchesCategory = selectedCategory === "All" || faq.category === selectedCategory;
    const matchesSearch = !searchQuery ||
      faq.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
      faq.answer.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleDelete = (id: string) => {
    setFaqs((prev) => prev.filter((f) => f.id !== id));
  };

  const handleAdd = () => {
    if (!newFaq.question.trim() || !newFaq.answer.trim()) return;
    setFaqs((prev) => [
      ...prev,
      { id: `faq_${Date.now()}`, ...newFaq, created_at: new Date().toISOString().split("T")[0] },
    ]);
    setNewFaq({ question: "", answer: "", category: "General" });
    setShowAddModal(false);
  };

  const handleUpdate = () => {
    if (!editingFaq) return;
    setFaqs((prev) => prev.map((f) => (f.id === editingFaq.id ? editingFaq : f)));
    setEditingFaq(null);
  };

  const handleSemanticSearch = () => {
    if (!searchQuery.trim()) return;
    // Simulate semantic search results
    setSemanticResults([
      { question: "What is the interest rate for home loans?", score: 0.95 },
      { question: "What are the foreclosure charges?", score: 0.87 },
      { question: "What is the processing fee for loans?", score: 0.82 },
      { question: "What is the maximum loan tenure?", score: 0.76 },
      { question: "How can I check my loan balance?", score: 0.71 },
    ]);
    setShowSemanticResults(true);
  };

  const handleDeleteAll = () => {
    if (window.confirm("Are you sure you want to delete ALL FAQs? This action cannot be undone.")) {
      setFaqs([]);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-gray-900" style={{ fontWeight: 700 }}>Knowledge Base</h1>
          <p className="text-gray-500" style={{ fontSize: 14 }}>
            Manage FAQs & vector store &middot; {faqs.length} entries
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowUploadModal(true)}
            className="px-3 py-2 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 transition-all flex items-center gap-2"
            style={{ fontSize: 13 }}
          >
            <Upload className="w-4 h-4" /> Upload PDF
          </button>
          <button
            className="px-3 py-2 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 transition-all flex items-center gap-2"
            style={{ fontSize: 13 }}
          >
            <Download className="w-4 h-4" /> Export
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-3 py-2 rounded-lg text-white transition-all flex items-center gap-2"
            style={{ background: "var(--brand-gradient)", fontSize: 13 }}
          >
            <Plus className="w-4 h-4" /> Add FAQ
          </button>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[240px] relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setShowSemanticResults(false); }}
              placeholder="Search FAQs..."
              className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-brand-main transition-colors"
              style={{ fontSize: 13 }}
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSemanticSearch(!semanticSearch)}
              className={`px-3 py-2 rounded-lg flex items-center gap-2 transition-all ${
                semanticSearch ? "text-white" : "border border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
              style={semanticSearch ? { background: "var(--brand-gradient)", fontSize: 13 } : { fontSize: 13 }}
            >
              <Sparkles className="w-4 h-4" /> Semantic
            </button>
            {semanticSearch && (
              <button
                onClick={handleSemanticSearch}
                className="px-3 py-2 rounded-lg bg-brand-dark text-white"
                style={{ fontSize: 13 }}
              >
                Search
              </button>
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  selectedCategory === cat
                    ? "text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
                style={selectedCategory === cat ? { background: "var(--brand-gradient)", fontSize: 12 } : { fontSize: 12 }}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Semantic Search Results */}
      {showSemanticResults && (
        <div className="bg-white rounded-xl p-4 border border-purple-200 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-gray-900 flex items-center gap-2" style={{ fontWeight: 600, fontSize: 14 }}>
              <Sparkles className="w-4 h-4 text-brand-main" /> Semantic Search Results
            </h3>
            <button onClick={() => setShowSemanticResults(false)} className="text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-2">
            {semanticResults.map((r) => (
              <div key={r.question} className="flex items-center justify-between p-2 rounded-lg bg-gray-50">
                <span style={{ fontSize: 13 }} className="text-gray-700">{r.question}</span>
                <span
                  className={`px-2 py-0.5 rounded-full ${
                    r.score > 0.9 ? "bg-green-100 text-green-700" :
                    r.score > 0.8 ? "bg-blue-100 text-blue-700" :
                    "bg-gray-100 text-gray-600"
                  }`}
                  style={{ fontSize: 11, fontWeight: 500 }}
                >
                  {(r.score * 100).toFixed(0)}% match
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* FAQ List */}
      <div className="space-y-3">
        {filtered.map((faq) => (
          <div key={faq.id} className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm hover:shadow-md transition-all">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5">
                  <span
                    className="px-2 py-0.5 rounded-full bg-brand-light/20 text-brand-dark"
                    style={{ fontSize: 11, fontWeight: 500 }}
                  >
                    {faq.category}
                  </span>
                  <span className="text-gray-400" style={{ fontSize: 11 }}>{faq.created_at}</span>
                </div>
                <h4 className="text-gray-900 mb-1" style={{ fontWeight: 600, fontSize: 14 }}>{faq.question}</h4>
                <p className="text-gray-600" style={{ fontSize: 13 }}>{faq.answer}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => setEditingFaq({ ...faq })}
                  className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-blue-500 transition-colors"
                >
                  <Edit3 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(faq.id)}
                  className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-red-500 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-100">
          <Database className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500" style={{ fontWeight: 500 }}>No FAQs found</p>
          <p className="text-gray-400" style={{ fontSize: 13 }}>Try adjusting your search or filters</p>
        </div>
      )}

      {/* Danger Zone */}
      <div className="bg-white rounded-xl p-4 border border-red-200 shadow-sm">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <div className="flex-1">
            <h4 className="text-red-700" style={{ fontWeight: 600, fontSize: 14 }}>Danger Zone</h4>
            <p className="text-red-500" style={{ fontSize: 12 }}>Delete all FAQs from the vector store. This cannot be undone.</p>
          </div>
          <button
            onClick={handleDeleteAll}
            className="px-3 py-1.5 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors flex items-center gap-2"
            style={{ fontSize: 13 }}
          >
            <Trash2 className="w-3 h-3" /> Delete All
          </button>
        </div>
      </div>

      {/* Add FAQ Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-gray-900" style={{ fontWeight: 600 }}>Add FAQ</h3>
              <button onClick={() => setShowAddModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label style={{ fontSize: 13 }}>Category</label>
                <select
                  value={newFaq.category}
                  onChange={(e) => setNewFaq({ ...newFaq, category: e.target.value })}
                  className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 outline-none"
                  style={{ fontSize: 13 }}
                >
                  {categories.filter((c) => c !== "All").map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                  <option value="Other">Other</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: 13 }}>Question</label>
                <input
                  value={newFaq.question}
                  onChange={(e) => setNewFaq({ ...newFaq, question: e.target.value })}
                  className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 outline-none"
                  placeholder="Enter the question..."
                  style={{ fontSize: 13 }}
                />
              </div>
              <div>
                <label style={{ fontSize: 13 }}>Answer</label>
                <textarea
                  value={newFaq.answer}
                  onChange={(e) => setNewFaq({ ...newFaq, answer: e.target.value })}
                  className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 outline-none h-28 resize-none"
                  placeholder="Enter the answer..."
                  style={{ fontSize: 13 }}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                style={{ fontSize: 13 }}
              >
                Cancel
              </button>
              <button
                onClick={handleAdd}
                className="px-4 py-2 rounded-lg text-white"
                style={{ background: "var(--brand-gradient)", fontSize: 13 }}
              >
                Add FAQ
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit FAQ Modal */}
      {editingFaq && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-gray-900" style={{ fontWeight: 600 }}>Edit FAQ</h3>
              <button onClick={() => setEditingFaq(null)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label style={{ fontSize: 13 }}>Category</label>
                <select
                  value={editingFaq.category}
                  onChange={(e) => setEditingFaq({ ...editingFaq, category: e.target.value })}
                  className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 outline-none"
                  style={{ fontSize: 13 }}
                >
                  {categories.filter((c) => c !== "All").map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 13 }}>Question</label>
                <input
                  value={editingFaq.question}
                  onChange={(e) => setEditingFaq({ ...editingFaq, question: e.target.value })}
                  className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 outline-none"
                  style={{ fontSize: 13 }}
                />
              </div>
              <div>
                <label style={{ fontSize: 13 }}>Answer</label>
                <textarea
                  value={editingFaq.answer}
                  onChange={(e) => setEditingFaq({ ...editingFaq, answer: e.target.value })}
                  className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 outline-none h-28 resize-none"
                  style={{ fontSize: 13 }}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setEditingFaq(null)}
                className="px-4 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                style={{ fontSize: 13 }}
              >
                Cancel
              </button>
              <button
                onClick={handleUpdate}
                className="px-4 py-2 rounded-lg text-white"
                style={{ background: "var(--brand-gradient)", fontSize: 13 }}
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload PDF Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-gray-900" style={{ fontWeight: 600 }}>Upload FAQ PDF</h3>
              <button onClick={() => setShowUploadModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-brand-main transition-colors cursor-pointer">
              <FileText className="w-10 h-10 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-600" style={{ fontSize: 14, fontWeight: 500 }}>Drop PDF file here or click to browse</p>
              <p className="text-gray-400 mt-1" style={{ fontSize: 12 }}>Supports Q&A format PDFs. Max 10MB.</p>
              <input type="file" accept=".pdf" className="hidden" />
            </div>
            <p className="text-gray-500 mt-3" style={{ fontSize: 12 }}>
              API: POST /agent/admin/faqs/upload-pdf (multipart/form-data)
            </p>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setShowUploadModal(false)}
                className="px-4 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                style={{ fontSize: 13 }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
