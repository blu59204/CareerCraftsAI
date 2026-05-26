'use client'

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { fadeUp, stagger } from '@/lib/motion-variants'
import { LiquidGlassButton } from '@/components/ui/LiquidGlassButton'
import { apiClient } from '@/lib/api'
import { toast } from 'sonner'
import { Building2, Globe, Newspaper, Code2 } from 'lucide-react'

interface CompanyData {
  company_name: string
  overview: string
  culture: string
  recent_news: string[]
  tech_stack: string[]
  glassdoor_sentiment: string
  last_researched: string
  partial_data?: string[]
}

export default function CompanyResearchPage() {
  const [query, setQuery] = useState('')
  const [company, setCompany] = useState('')

  const { data, isLoading } = useQuery<CompanyData>({
    queryKey: ['company', company],
    queryFn: () => apiClient.get(`/api/v1/company/research?name=${encodeURIComponent(company)}`).then(r => r.data),
    enabled: !!company,
  })

  const mutation = useMutation({
    mutationFn: (force: boolean) =>
      apiClient.post('/api/v1/company/research', { company_name: query || company, force_refresh: force }).then(r => r.data),
    onSuccess: (res: CompanyData) => {
      setCompany(res.company_name)
      if (res.partial_data?.length) {
        toast.warning(`Some sources failed: ${res.partial_data.join(', ')}`)
      }
    },
    onError: () => toast.error('Research failed'),
  })

  const handleSearch = () => {
    if (!query.trim()) return
    setCompany(query.trim())
    mutation.mutate(false)
  }

  const result = mutation.data || data

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="flex items-center gap-2 text-2xl font-bold">
        <Building2 className="h-6 w-6" /> Company Research
      </h1>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded-md border bg-background px-3 py-2"
          placeholder="Enter company name..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
        />
        <LiquidGlassButton onClick={handleSearch} disabled={mutation.isPending}>
          {mutation.isPending ? 'Researching...' : 'Research'}
        </LiquidGlassButton>
      </div>

      {result && (
        <motion.div variants={stagger} initial="hidden" animate="visible" className="space-y-5">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Last researched: {new Date(result.last_researched).toLocaleString()}</span>
            <LiquidGlassButton onClick={() => mutation.mutate(true)} disabled={mutation.isPending}>
              Force Refresh
            </LiquidGlassButton>
          </div>

          {result.partial_data?.length && (
            <p className="text-sm text-yellow-600">⚠️ Partial data — failed sources: {result.partial_data.join(', ')}</p>
          )}

          <motion.section variants={fadeUp}>
            <h2 className="flex items-center gap-2 font-semibold"><Globe className="h-4 w-4" /> Overview</h2>
            <p className="mt-1 text-sm text-muted-foreground">{result.overview}</p>
          </motion.section>

          <motion.section variants={fadeUp}>
            <h2 className="font-semibold">Culture</h2>
            <p className="mt-1 text-sm text-muted-foreground">{result.culture}</p>
          </motion.section>

          <motion.section variants={fadeUp}>
            <h2 className="flex items-center gap-2 font-semibold"><Newspaper className="h-4 w-4" /> Recent News</h2>
            <ul className="mt-1 list-inside list-disc text-sm text-muted-foreground">
              {result.recent_news.map((item, i) => <li key={i}>{item}</li>)}
            </ul>
          </motion.section>

          <motion.section variants={fadeUp}>
            <h2 className="flex items-center gap-2 font-semibold"><Code2 className="h-4 w-4" /> Tech Stack</h2>
            <div className="mt-1 flex flex-wrap gap-2">
              {result.tech_stack.map(tech => (
                <span key={tech} className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium">{tech}</span>
              ))}
            </div>
          </motion.section>

          <motion.section variants={fadeUp}>
            <h2 className="font-semibold">Glassdoor Sentiment</h2>
            <p className="mt-1 text-sm text-muted-foreground">{result.glassdoor_sentiment}</p>
          </motion.section>
        </motion.div>
      )}

      {isLoading && !mutation.data && <p className="text-sm text-muted-foreground">Loading...</p>}
    </div>
  )
}
