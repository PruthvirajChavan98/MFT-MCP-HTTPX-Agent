import { useCallback, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Copy,
  Database,
  FileText,
  Loader2,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { toast } from 'sonner'

import { clearAllFaqs, deleteFaq, ingestFaqBatch, ingestFaqPdf, updateFaq } from '@features/admin/api/admin'
import { Alert, AlertDescription } from '@components/ui/alert'
import { Skeleton } from '@components/ui/skeleton'
import { MobileHeader } from '@components/ui/mobile-header'
import { CollapsiblePanel } from '@components/ui/collapsible-panel'
import { useAdminContext } from '@features/admin/context/AdminContext'
import {
  buildKnowledgeBaseViewModel,
  type KnowledgeBaseFaqRow,
  type KnowledgeBaseSortDir,
  type KnowledgeBaseSortField,
} from './viewmodel'
import {
  faqCategoriesQueryOptions,
  faqListQueryOptions,
  faqSemanticSearchQueryOptions,
} from '@features/admin/query/queryOptions'
import { type SemanticMatch, DEFAULT_CATEGORY, getErrorMessage } from './components/kb-types'
import { FAQRow } from './components/FaqRow'
import { AddEditFaqModal } from './components/AddEditFaqModal'

// ────────────────────────────────────────────────────────────────────────────
// Main Component
// ────────────────────────────────────────────────────────────────────────────

export function KnowledgeBasePage() {
  const auth = useAdminContext()
  const queryClient = useQueryClient()

  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('All')
  const [sortField, setSortField] = useState<KnowledgeBaseSortField>('createdAt')
  const [sortDir, setSortDir] = useState<KnowledgeBaseSortDir>('desc')
  const [modalOpen, setModalOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<KnowledgeBaseFaqRow | null>(null)
  const [modalSaving, setModalSaving] = useState(false)
  const [semanticMenuOpen, setSemanticMenuOpen] = useState<number | null>(null)

  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const faqsQuery = useQuery(faqListQueryOptions(auth.adminKey, 500, 0))
  const categoriesQuery = useQuery(faqCategoriesQueryOptions(auth.adminKey))

  const semanticQuery = useQuery(
    faqSemanticSearchQueryOptions({
      adminKey: auth.adminKey,
      query: searchQuery.trim(),
      limit: 5,
    }),
  )

  const semanticMatches: SemanticMatch[] = semanticQuery.data ?? []

  const model = useMemo(
    () =>
      buildKnowledgeBaseViewModel({
        faqs: faqsQuery.data ?? [],
        categories: categoriesQuery.data ?? [],
        selectedCategory,
        sortField,
        sortDir,
      }),
    [faqsQuery.data, categoriesQuery.data, selectedCategory, sortField, sortDir],
  )

  const findFaqByQuestion = (question: string): KnowledgeBaseFaqRow | undefined =>
    model.rows.find((r) => r.question === question)

  const availableCategories = useMemo(() => {
    const labels = categoriesQuery.data?.map((category) => category.label) ?? []
    return labels.length > 0 ? labels : [DEFAULT_CATEGORY]
  }, [categoriesQuery.data])

  const deleteMut = useMutation({
    mutationFn: (row: KnowledgeBaseFaqRow) =>
      deleteFaq(auth.adminKey, row.serverId ? { id: row.serverId } : { question: row.question }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['faqs'] })
      toast.success('FAQ deleted')
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const deleteAllMut = useMutation({
    mutationFn: () => clearAllFaqs(auth.adminKey),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['faqs'] })
      toast.success('All FAQs deleted')
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const handleDeleteAll = () => {
    if (model.stats.total === 0) return
    if (!window.confirm(`Delete all ${model.stats.total} FAQs? This cannot be undone.`)) return
    deleteAllMut.mutate()
  }

  const runSemanticSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      toast.error('Enter a semantic search query')
      return
    }
    const result = await semanticQuery.refetch()
    if (result.error) {
      toast.error(getErrorMessage(result.error))
    }
  }, [searchQuery, semanticQuery])

  const handleSort = (field: KnowledgeBaseSortField) => {
    if (sortField === field) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortField(field)
    setSortDir('asc')
  }

  const openAddModal = () => {
    setEditTarget(null)
    setModalOpen(true)
  }

  const openEditModal = (row: KnowledgeBaseFaqRow) => {
    setEditTarget(row)
    setModalOpen(true)
  }

  const closeModal = () => {
    setModalOpen(false)
    setEditTarget(null)
  }

  const handleSaveEntries = async (
    entries: Array<{ question: string; answer: string; category: string; tags: string[] }>,
  ) => {
    setModalSaving(true)
    try {
      if (editTarget) {
        await updateFaq(auth.adminKey, {
          ...(editTarget.serverId ? { id: editTarget.serverId } : { original_question: editTarget.question }),
          new_question: entries[0].question,
          new_answer: entries[0].answer,
          new_category: entries[0].category,
          new_tags: entries[0].tags,
        })
        toast.success('FAQ updated')
      } else {
        await ingestFaqBatch(auth.adminKey, entries)
        toast.success(
          entries.length === 1
            ? 'FAQ added and queued for vectorization'
            : `${entries.length} FAQs added and queued for vectorization`,
        )
      }

      await queryClient.invalidateQueries({ queryKey: ['faqs'] })
      closeModal()
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setModalSaving(false)
    }
  }

  const handlePdfIngest = async () => {
    if (!pdfFile) return
    setPdfLoading(true)
    try {
      await ingestFaqPdf(auth.adminKey, pdfFile)
      toast.success(`PDF parsed and ingested successfully`)
      setPdfFile(null)
      if (fileRef.current) fileRef.current.value = ''
      await queryClient.invalidateQueries({ queryKey: ['faqs'] })
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setPdfLoading(false)
    }
  }

  if (faqsQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{getErrorMessage(faqsQuery.error)}</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="flex flex-col md:flex-row h-full min-h-0">
      {/* ── Left main panel ──────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-auto px-4 sm:px-8 py-5 sm:py-7">
        {/* Header */}
        <MobileHeader
          title="Knowledge Base"
          description="Manage FAQs and vector embeddings."
          actions={
            <>
              <button
                onClick={handleDeleteAll}
                disabled={deleteAllMut.isPending || model.stats.total === 0}
                className="flex items-center gap-2 px-4 py-2.5 border border-red-200 text-red-600 hover:bg-red-50 rounded-xl text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {deleteAllMut.isPending ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                Delete All
              </button>
              <button
                onClick={openAddModal}
                className="flex items-center gap-2 px-4 py-2.5 bg-teal-500 hover:bg-teal-600 text-white rounded-xl text-sm transition-all shadow-sm shadow-teal-200 active:scale-95"
              >
                <Plus size={16} />
                Add FAQ
              </button>
              <button
                onClick={() => fileRef.current?.click()}
                className="flex items-center gap-2 px-4 py-2.5 border border-gray-200 text-gray-700 hover:bg-gray-50 rounded-xl text-sm transition-all md:hidden"
              >
                <Upload size={16} />
                Upload PDF
              </button>
            </>
          }
          className="mb-6"
        />

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-100 px-5 py-4 shadow-sm">
            {faqsQuery.isLoading ? <Skeleton className="h-8 w-16" /> : (
              <p className="text-2xl font-semibold text-gray-800">{model.stats.total}</p>
            )}
            <p className="text-xs text-gray-400 mt-0.5">Total FAQs</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 px-5 py-4 shadow-sm">
            {faqsQuery.isLoading ? <Skeleton className="h-8 w-16" /> : (
              <p className="text-2xl font-semibold text-teal-600">{model.stats.vectorized}</p>
            )}
            <p className="text-xs text-gray-400 mt-0.5">Vectorized</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 px-5 py-4 shadow-sm">
            {faqsQuery.isLoading ? <Skeleton className="h-8 w-16" /> : (
              <span className="flex items-center gap-1.5">
                <p className="text-2xl font-semibold text-amber-600">
                  {model.stats.pending + model.stats.syncing}
                </p>
                {model.stats.syncing > 0 && (
                  <Loader2 size={14} className="animate-spin text-amber-500 mt-1" />
                )}
              </span>
            )}
            <p className="text-xs text-gray-400 mt-0.5">Pending sync</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 px-5 py-4 shadow-sm">
            {faqsQuery.isLoading ? <Skeleton className="h-8 w-16" /> : (
              <p className={`text-2xl font-semibold ${model.stats.failed > 0 ? 'text-rose-600' : 'text-gray-300'}`}>
                {model.stats.failed}
              </p>
            )}
            <p className="text-xs text-gray-400 mt-0.5">Failed</p>
          </div>
        </div>

        {/* Search bar — always semantic */}
        <div className="flex items-center gap-3 mb-4">
          <div className="relative flex-1">
            <Search
              size={16}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void runSemanticSearch()
              }}
              placeholder="Describe what you're looking for…"
              className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm bg-white text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:border-transparent transition-all shadow-sm"
            />
          </div>
          <button
            type="button"
            onClick={() => void runSemanticSearch()}
            disabled={semanticQuery.isFetching}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm border transition-all shadow-sm whitespace-nowrap bg-teal-500 border-teal-500 text-white shadow-teal-200 hover:bg-teal-600 disabled:opacity-60"
          >
            {semanticQuery.isFetching
              ? <Loader2 size={15} className="animate-spin" />
              : <Sparkles size={15} />
            }
            Semantic Search
          </button>
        </div>

        {categoriesQuery.error && (
          <Alert className="mb-4 border-amber-200 bg-amber-50 text-amber-700">
            <AlertDescription>
              Category catalog unavailable: {getErrorMessage(categoriesQuery.error)}. Falling back to FAQ-derived categories.
            </AlertDescription>
          </Alert>
        )}

        {/* Category pills + sort — two independent rows, no layout conflict */}
        <div className="mb-5 space-y-2">
          {/* Row 1: scrollable category pills — isolated scroll context */}
          <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {model.categoryOptions.map((category) => (
              <button
                key={category.id}
                onClick={() => setSelectedCategory(category.label)}
                className={[
                  "px-3 py-1.5 rounded-lg text-xs whitespace-nowrap transition-all border",
                  selectedCategory === category.label
                    ? "bg-teal-500 text-white border-teal-500 shadow-sm"
                    : "bg-white text-gray-500 border-gray-200 hover:border-teal-200 hover:text-teal-600",
                ].join(" ")}
              >
                {category.label}
                {category.label !== "All" && (
                  <span className="ml-1.5 opacity-60">{category.count}</span>
                )}
              </button>
            ))}
          </div>
          {/* Row 2: sort controls — always fully visible, right-aligned */}
          <div className="flex items-center justify-end gap-2">
            <span className="text-xs text-gray-400">Sort by:</span>
            {(["question", "category", "createdAt"] as KnowledgeBaseSortField[]).map((f) => (
              <button
                key={f}
                onClick={() => handleSort(f)}
                className={[
                  "px-2.5 py-1.5 rounded-lg text-xs border transition-all",
                  sortField === f
                    ? "bg-gray-800 text-white border-gray-800"
                    : "bg-white text-gray-500 border-gray-200 hover:border-gray-300",
                ].join(" ")}
              >
                {f === "createdAt" ? "Date" : f.charAt(0).toUpperCase() + f.slice(1)}
                {sortField === f && (sortDir === "asc" ? " ↑" : " ↓")}
              </button>
            ))}
          </div>
        </div>

        {(semanticQuery.isFetching || semanticMatches.length > 0) && (
          <div className="mb-5 rounded-2xl border border-violet-100 bg-violet-50/50 p-5">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-violet-900">
              <Sparkles className="size-4" />
              Semantic Matches
            </h3>
            {semanticQuery.isFetching ? (
              <div className="space-y-2">
                <Skeleton className="h-16 rounded-lg" />
                <Skeleton className="h-16 rounded-lg" />
              </div>
            ) : (
              <div className="space-y-3">
                {semanticMatches.map((match, index) => (
                  <div key={`${match.question}:${index}`} className="flex items-start gap-4 rounded-lg border border-violet-100 bg-white p-4 shadow-sm">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-bold text-gray-900">{match.question}</p>
                      <p className="mt-1 line-clamp-2 text-sm text-gray-600">{match.answer}</p>
                    </div>
                    <span className="shrink-0 rounded-full border border-emerald-200 bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-700">
                      {(match.score * 100).toFixed(1)}% Match
                    </span>
                    <div className="relative shrink-0">
                      <button
                        type="button"
                        onClick={() => setSemanticMenuOpen(semanticMenuOpen === index ? null : index)}
                        aria-label="Open row actions"
                        className="rounded-lg p-1.5 text-gray-400 transition-all hover:bg-gray-100 hover:text-gray-700"
                      >
                        <MoreHorizontal size={16} />
                      </button>
                      {semanticMenuOpen === index && (
                        <>
                          <div className="fixed inset-0 z-10" onClick={() => setSemanticMenuOpen(null)} aria-hidden />
                          <div className="absolute right-0 top-8 z-20 w-36 overflow-hidden rounded-xl border border-gray-100 bg-white py-1 shadow-xl">
                            <button
                              type="button"
                              onClick={() => {
                                const faq = findFaqByQuestion(match.question)
                                if (faq) openEditModal(faq)
                                setSemanticMenuOpen(null)
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
                            >
                              <Pencil size={13} />
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={async () => {
                                await navigator.clipboard.writeText(`Q: ${match.question}\nA: ${match.answer}`)
                                toast.success('Copied to clipboard')
                                setSemanticMenuOpen(null)
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
                            >
                              <Copy size={13} />
                              Copy
                            </button>
                            <div className="my-1 border-t border-gray-100" />
                            <button
                              type="button"
                              onClick={() => {
                                const faq = findFaqByQuestion(match.question)
                                if (faq) deleteMut.mutate(faq)
                                setSemanticMenuOpen(null)
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 transition-colors hover:bg-red-50"
                            >
                              <Trash2 size={13} />
                              Delete
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* FAQ list */}
        <div className="flex-1">
          {faqsQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-24 rounded-xl" />
              <Skeleton className="h-24 rounded-xl" />
              <Skeleton className="h-24 rounded-xl" />
            </div>
          ) : model.rows.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
                <Database size={28} className="text-gray-300" />
              </div>
              <p className="text-gray-500 font-medium">
                {searchQuery || selectedCategory !== "All"
                  ? "No FAQs match your filters"
                  : "No FAQs yet"}
              </p>
              <p className="text-sm text-gray-400 mt-1 max-w-xs">
                {searchQuery
                  ? "Try a different search term or clear filters"
                  : "Click \u201cAdd FAQ\u201d to create your first entry."}
              </p>
              {(searchQuery || selectedCategory !== "All") && (
                <button
                  onClick={() => { setSearchQuery(""); setSelectedCategory("All"); }}
                  className="mt-4 px-4 py-2 text-sm text-teal-600 border border-teal-200 rounded-lg hover:bg-teal-50 transition-colors"
                >
                  Clear filters
                </button>
              )}
            </div>
          ) : (
            <>
              <p className="text-xs text-gray-400 mb-3">
                Showing {model.rows.length} of {model.stats.total} entries
              </p>
              {model.rows.map((faq) => (
                <FAQRow key={faq.id} faq={faq} onEdit={openEditModal} onDelete={(row) => deleteMut.mutate(row)} />
              ))}
            </>
          )}
        </div>
      </div>

      {/* ── Right panel ──────────────────────────────────────────────────── */}
      <CollapsiblePanel
        title="PDF Upload"
        collapseBelow="md"
        className="md:w-75 shrink-0 md:border-l border-gray-200 bg-white md:overflow-auto"
      >
        <div className="px-6 py-6 space-y-8">

          {/* PDF FAQ Upload */}
          <section>
            <div className="flex items-center gap-2 mb-1">
              <FileText size={16} className="text-gray-700" />
              <h3 className="text-sm font-semibold text-gray-900">PDF FAQ Upload</h3>
            </div>
            <p className="text-xs text-gray-500 mb-4 leading-relaxed">
              Upload a PDF containing{" "}
              <code className="text-pink-600 bg-pink-50 px-1 rounded">Question:</code> /{" "}
              <code className="text-teal-600 bg-teal-50 px-1 rounded">Answer:</code> blocks.
              Q&A pairs are extracted automatically.
            </p>

            <div
              className={[
                "border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all",
                pdfFile
                  ? "border-teal-300 bg-teal-50"
                  : "border-gray-200 hover:border-teal-300 hover:bg-teal-50/30",
              ].join(" ")}
              onClick={() => fileRef.current?.click()}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) {
                    if (f.type !== "application/pdf") {
                      toast.error("Only PDF files are supported");
                      return;
                    }
                    setPdfFile(f);
                  }
                }}
              />
              {pdfFile ? (
                <div className="flex items-center gap-2 justify-center text-teal-700">
                  <FileText size={18} className="text-teal-500" />
                  <span className="text-sm truncate max-w-40">{pdfFile.name}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setPdfFile(null);
                      if (fileRef.current) fileRef.current.value = "";
                    }}
                    className="ml-1 text-gray-400 hover:text-gray-600"
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div>
                  <Upload size={22} className="mx-auto text-gray-300 mb-2" />
                  <p className="text-xs text-gray-500">Click to choose a PDF, or drag & drop</p>
                  <p className="text-xs text-gray-400 mt-0.5">PDF up to 25 MB</p>
                </div>
              )}
            </div>

            <button
              onClick={handlePdfIngest}
              disabled={!pdfFile || pdfLoading}
              className="mt-3 w-full py-2.5 rounded-xl text-sm font-medium bg-teal-500 hover:bg-teal-600 text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm shadow-teal-200"
            >
              {pdfLoading ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Parsing PDF…
                </>
              ) : (
                <>
                  <FileText size={15} />
                  Ingest PDF
                </>
              )}
            </button>
          </section>

          {/* Divider */}
          <div className="border-t border-gray-100" />

          {/* Tips */}
          <section>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Tips
            </h3>
            <div className="space-y-2.5">
              {[
                'Click "Add FAQ" then "Add another FAQ" to create multiple at once',
                "Vectorization runs async after ingest — check Status column",
                "Semantic search requires at least 1 vectorized FAQ",
              ].map((tip, i) => (
                <div key={i} className="flex gap-2 text-xs text-gray-500">
                  <span className="shrink-0 w-4 h-4 rounded-full bg-teal-50 text-teal-600 flex items-center justify-center text-[10px] font-semibold mt-0.5">
                    {i + 1}
                  </span>
                  {tip}
                </div>
              ))}
            </div>
          </section>
        </div>
      </CollapsiblePanel>

      {/* Modal */}
      {modalOpen && (
        <AddEditFaqModal
          initial={editTarget}
          categories={availableCategories}
          saving={modalSaving}
          onSave={handleSaveEntries}
          onClose={closeModal}
        />
      )}
    </div>
  )
}
