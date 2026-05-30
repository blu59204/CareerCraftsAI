'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { fadeUp, stagger } from '@/lib/motion-variants'
import { LiquidGlassButton } from '@/components/ui/LiquidGlassButton'
import { CommandHeader } from '@/components/immersive/CommandHeader'
import { apiClient } from '@/lib/api'
import { toast } from 'sonner'
import { TrendingUp, BarChart3 } from 'lucide-react'

// Matches backend SalaryReport DB model (salary_reports table)
interface SalaryReport {
  id: string
  p25: number
  p50: number
  p75: number
  classification: 'below_market' | 'at_market' | 'above_market' | null
  negotiation_script: Record<string, unknown> | null
  data_unavailable: boolean
}

export default function SalaryPage() {
  const [role, setRole] = useState('')
  const [company, setCompany] = useState('')
  const [location, setLocation] = useState('')
  const [offerAmount, setOfferAmount] = useState('')
  const [report, setReport] = useState<SalaryReport | null>(null)

  // Backend runs the agent synchronously then returns {run_id}. The SalaryReport
  // row shares the run_id as its primary key, so we fetch it by that id.
  const mutation = useMutation({
    mutationFn: async (data: { role: string; company?: string; location?: string; offer_amount?: number }) => {
      const { data: started } = await apiClient.post<{ run_id: string; status: string }>('/salary/report', data)
      const { data: full } = await apiClient.get<SalaryReport>(`/salary/report/${started.run_id}`)
      return full
    },
    onSuccess: (data) => {
      setReport(data)
      if (data.data_unavailable) {
        toast.warning('Not enough market data found for this role')
      } else {
        toast.success('Salary report generated')
      }
    },
    onError: () => toast.error('Failed to generate report'),
  })

  const approveMutation = useMutation({
    mutationFn: (reportId: string) =>
      apiClient.post(`/agents/${reportId}/approve`, { approved: true }),
    onSuccess: () => toast.success('Negotiation script approved'),
    onError: () => toast.error('Approval failed'),
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

  const formatScript = (script: Record<string, unknown> | null): string => {
    if (!script) return 'No negotiation script available.'
    // negotiation_script is a JSON object; render it readably.
    return Object.entries(script)
      .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
      .join('\n\n')
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
          placeholder="Offer amount (optional)"
          value={offerAmount}
          onChange={e => setOfferAmount(e.target.value)}
          className="w-full rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm"
        />
        <LiquidGlassButton type="submit" disabled={mutation.isPending} className="w-full md:col-span-2">
          {mutation.isPending ? 'Generating...' : 'Generate Report'}
        </LiquidGlassButton>
      </motion.form>

      {report && (
        <motion.div variants={fadeUp} className="glass-panel space-y-6 rounded-3xl p-6">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            <h2 className="text-lg font-semibold">Market Percentiles</h2>
          </div>

          <div className="space-y-3">
            {(['p25', 'p50', 'p75'] as const).map(key => (
              <div key={key} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="uppercase text-muted-foreground">{key}</span>
                  <span className="font-mono">${report[key].toLocaleString()}</span>
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
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">{formatScript(report.negotiation_script)}</p>
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
