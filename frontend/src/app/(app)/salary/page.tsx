'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { fadeUp, stagger } from '@/lib/motion-variants'
import { LiquidGlassButton } from '@/components/ui/LiquidGlassButton'
import { CommandHeader } from '@/components/immersive/CommandHeader'
import { apiClient, getApiErrorMessage } from '@/lib/api'
import { startAgentRun, waitForAgentRun } from '@/lib/agent-run'
import { toast } from 'sonner'
import { TrendingUp, BarChart3 } from 'lucide-react'

// Matches the shape we render from the salary_intelligence agent's run
// output — see backend/app/agents/salary_agent.py (report + negotiation
// script). `id` is the agent run id, used for the approve/discard actions.
interface SalaryReport {
  id: string
  p25: number
  p50: number
  p75: number
  classification: 'below_market' | 'at_market' | 'above_market' | null
  negotiation_script: Record<string, unknown> | null
  data_unavailable: boolean
  currency: string
  sample_size: number | null
  sources: string[]
}

function formatMoney(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(amount)
  } catch {
    return amount.toLocaleString()
  }
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export default function SalaryPage() {
  const [role, setRole] = useState('')
  const [company, setCompany] = useState('')
  const [location, setLocation] = useState('')
  const [offerAmount, setOfferAmount] = useState('')
  const [report, setReport] = useState<SalaryReport | null>(null)

  // The agent can run up to 120s server-side, so we start it and poll for a
  // terminal status instead of holding one long HTTP request open. Data-rich
  // runs land in "awaiting_approval" (HITL gate on the negotiation script);
  // "data_unavailable" runs land in "completed" with a flat result.
  const mutation = useMutation({
    mutationFn: async (data: { role: string; company?: string; location?: string; offer_amount?: number }) => {
      const runId = await startAgentRun('salary_intelligence', data)
      const run = await waitForAgentRun(runId)
      if (run.status !== 'completed' && run.status !== 'awaiting_approval') {
        throw new Error(run.error || `Salary report ${run.status}`)
      }
      const output = (run.output ?? {}) as Record<string, unknown>
      const reportData = (output.report as Record<string, unknown> | undefined) ?? output
      const script = (output.script as Record<string, unknown> | undefined) ?? null
      const result: SalaryReport = {
        id: runId,
        p25: Number(reportData.p25 ?? 0),
        p50: Number(reportData.p50 ?? 0),
        p75: Number(reportData.p75 ?? 0),
        classification: (reportData.classification as SalaryReport['classification']) ?? null,
        negotiation_script: script,
        data_unavailable: Boolean(reportData.data_unavailable),
        currency: String(reportData.currency ?? 'USD'),
        sample_size: typeof reportData.sample_size === 'number' ? reportData.sample_size : null,
        sources: Array.isArray(reportData.data_sources) ? (reportData.data_sources as string[]) : [],
      }
      return result
    },
    onSuccess: (data) => {
      setReport(data)
      if (data.data_unavailable) {
        toast.warning('Not enough market data found for this role')
      } else {
        toast.success('Salary report generated')
      }
    },
    onError: (error) => toast.error(getApiErrorMessage(error, error instanceof Error ? error.message : 'Failed to generate report')),
  })

  const approveMutation = useMutation({
    mutationFn: (reportId: string) =>
      apiClient.post(`/agents/${reportId}/approve`, { approved: true }),
    onSuccess: () => toast.success('Negotiation script approved'),
    onError: (error) => toast.error(getApiErrorMessage(error, 'Approval failed')),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!role.trim()) return toast.error('Role is required')
    mutation.mutate({
      role,
      ...(company && { company }),
      ...(location && { location }),
      ...(offerAmount && { offer_amount: Number(offerAmount) }),
    })
  }

  const maxVal = report ? Math.max(report.p75, 1) : 1

  const classificationColor: Record<string, string> = {
    below_market: 'bg-danger/20 text-danger border-danger/30',
    at_market: 'bg-warning/20 text-warning border-warning/30',
    above_market: 'bg-success/20 text-success border-success/30',
  }

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="mx-auto max-w-5xl space-y-8">
      <CommandHeader
        eyebrow="Dashboard UI"
        title="Salary Intelligence"
        description="Benchmark offers, compare percentiles, and generate approval-safe negotiation scripts."
      />

      <motion.form variants={fadeUp} onSubmit={handleSubmit} className="glass-panel grid gap-3 rounded-3xl p-6 md:grid-cols-2">
        <input
          type="text"
          placeholder="Role *"
          value={role}
          onChange={e => setRole(e.target.value)}
          className="w-full rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm"
          required
        />
        <input
          type="text"
          placeholder="Company (optional)"
          value={company}
          onChange={e => setCompany(e.target.value)}
          className="w-full rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm"
        />
        <input
          type="text"
          placeholder="Location (optional)"
          value={location}
          onChange={e => setLocation(e.target.value)}
          className="w-full rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm"
        />
        <input
          type="number"
          placeholder="Your offer, annual (optional)"
          value={offerAmount}
          onChange={e => setOfferAmount(e.target.value)}
          className="w-full rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm"
        />
        <LiquidGlassButton type="submit" disabled={mutation.isPending} className="w-full md:col-span-2">
          {mutation.isPending ? 'Generating...' : 'Generate Report'}
        </LiquidGlassButton>
      </motion.form>

      {report?.data_unavailable && (
        <motion.div variants={fadeUp} className="glass-panel rounded-3xl p-6 text-sm text-muted-foreground">
          Not enough published salary figures were found for this role. Try a more common title
          (for example &ldquo;Backend Engineer&rdquo;), add a location, or leave the company out to see the wider market.
        </motion.div>
      )}

      {report && !report.data_unavailable && (
        <motion.div variants={fadeUp} className="glass-panel space-y-6 rounded-3xl p-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              <h2 className="text-lg font-semibold">Market Percentiles</h2>
            </div>
            {report.sample_size ? (
              <span className="text-xs text-muted-foreground">
                Annual, from {report.sample_size} published figures
              </span>
            ) : null}
          </div>

          <div className="space-y-3">
            {(['p25', 'p50', 'p75'] as const).map(key => (
              <div key={key} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="uppercase text-muted-foreground">{key}</span>
                  <span className="font-mono">{formatMoney(report[key], report.currency)}</span>
                </div>
                <div className="h-3 rounded-full bg-muted overflow-hidden">
                  <motion.div
                    className="h-full rounded-full bg-primary"
                    initial={{ width: 0 }}
                    animate={{ width: `${(report[key] / maxVal) * 100}%` }}
                    transition={{ duration: 0.6 }}
                  />
                </div>
              </div>
            ))}
          </div>

          {report.sources.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Sources:{' '}
              {report.sources.map((url, i) => (
                <span key={url}>
                  {i > 0 && ', '}
                  <a href={url} target="_blank" rel="noopener noreferrer" className="hover:text-primary hover:underline">
                    {hostname(url)}
                  </a>
                </span>
              ))}
            </p>
          )}

          {report.classification && (
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              <span className="text-sm font-medium">Offer Classification:</span>
              <span className={`px-2 py-0.5 rounded border text-xs font-semibold ${classificationColor[report.classification] ?? ''}`}>
                {report.classification.replace('_', ' ').toUpperCase()}
              </span>
            </div>
          )}

          <div className="space-y-3 rounded-lg border p-4">
            <h3 className="font-semibold">Negotiation Script</h3>
            {report.negotiation_script ? (
              <div className="space-y-3 text-sm text-muted-foreground">
                {typeof report.negotiation_script.opening === 'string' && (
                  <p className="whitespace-pre-wrap">{report.negotiation_script.opening}</p>
                )}
                {typeof report.negotiation_script.counter_offer === 'number' && (
                  <p>
                    <span className="font-medium text-foreground">Counter-offer: </span>
                    {formatMoney(report.negotiation_script.counter_offer, report.currency)}
                  </p>
                )}
                {Array.isArray(report.negotiation_script.justifications) && (
                  <ul className="list-disc space-y-1 pl-5">
                    {(report.negotiation_script.justifications as unknown[]).map((item, i) => (
                      <li key={i}>{String(item)}</li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No negotiation script available.</p>
            )}
            <div className="flex gap-2 pt-2">
              <LiquidGlassButton
                onClick={() => approveMutation.mutate(report.id)}
                disabled={approveMutation.isPending}
              >
                {approveMutation.isPending ? 'Approving...' : 'Approve & Use'}
              </LiquidGlassButton>
              <LiquidGlassButton
                onClick={() => toast.info('Script discarded')}
                className="opacity-60"
              >
                Discard
              </LiquidGlassButton>
            </div>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
