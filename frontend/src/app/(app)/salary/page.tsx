'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { fadeUp, stagger } from '@/lib/motion-variants'
import { LiquidGlassButton } from '@/components/ui/LiquidGlassButton'
import { apiClient } from '@/lib/api'
import { toast } from 'sonner'
import { DollarSign, TrendingUp, BarChart3 } from 'lucide-react'

interface SalaryReport {
  p25: number
  p50: number
  p75: number
  offer_classification: 'below' | 'at' | 'above'
  negotiation_script: string
  report_id: string
}

export default function SalaryPage() {
  const [role, setRole] = useState('')
  const [company, setCompany] = useState('')
  const [location, setLocation] = useState('')
  const [offerAmount, setOfferAmount] = useState('')
  const [report, setReport] = useState<SalaryReport | null>(null)

  const mutation = useMutation({
    mutationFn: (data: { role: string; company?: string; location?: string; offer_amount?: number }) =>
      apiClient.post<SalaryReport>('/api/v1/salary/report', data).then(r => r.data),
    onSuccess: (data) => {
      setReport(data)
      toast.success('Salary report generated')
    },
    onError: () => toast.error('Failed to generate report'),
  })

  const approveMutation = useMutation({
    mutationFn: (reportId: string) =>
      apiClient.post(`/api/v1/agents/${reportId}/approve`, { action: 'approve' }),
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

  const classificationColor = {
    below: 'bg-red-500/20 text-red-400 border-red-500/30',
    at: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    above: 'bg-green-500/20 text-green-400 border-green-500/30',
  }

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="max-w-2xl mx-auto p-6 space-y-8">
      <motion.div variants={fadeUp} className="flex items-center gap-3">
        <DollarSign className="h-8 w-8 text-primary" />
        <h1 className="text-2xl font-bold">Salary Intelligence</h1>
      </motion.div>

      <motion.form variants={fadeUp} onSubmit={handleSubmit} className="space-y-4">
        <input
          type="text"
          placeholder="Role *"
          value={role}
          onChange={e => setRole(e.target.value)}
          className="w-full rounded-lg border bg-background px-4 py-2"
          required
        />
        <input
          type="text"
          placeholder="Company (optional)"
          value={company}
          onChange={e => setCompany(e.target.value)}
          className="w-full rounded-lg border bg-background px-4 py-2"
        />
        <input
          type="text"
          placeholder="Location (optional)"
          value={location}
          onChange={e => setLocation(e.target.value)}
          className="w-full rounded-lg border bg-background px-4 py-2"
        />
        <input
          type="number"
          placeholder="Offer amount (optional)"
          value={offerAmount}
          onChange={e => setOfferAmount(e.target.value)}
          className="w-full rounded-lg border bg-background px-4 py-2"
        />
        <LiquidGlassButton type="submit" disabled={mutation.isPending} className="w-full">
          {mutation.isPending ? 'Generating...' : 'Generate Report'}
        </LiquidGlassButton>
      </motion.form>

      {report && (
        <motion.div variants={fadeUp} className="space-y-6">
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

          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            <span className="text-sm font-medium">Offer Classification:</span>
            <span className={`px-2 py-0.5 rounded border text-xs font-semibold ${classificationColor[report.offer_classification]}`}>
              {report.offer_classification.toUpperCase()} MARKET
            </span>
          </div>

          <div className="space-y-3 rounded-lg border p-4">
            <h3 className="font-semibold">Negotiation Script</h3>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">{report.negotiation_script}</p>
            <div className="flex gap-2 pt-2">
              <LiquidGlassButton
                onClick={() => approveMutation.mutate(report.report_id)}
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
