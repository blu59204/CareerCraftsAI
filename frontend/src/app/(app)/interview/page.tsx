'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { fadeUp, stagger } from '@/lib/motion-variants'
import { LiquidGlassButton } from '@/components/ui/LiquidGlassButton'
import { CommandHeader } from '@/components/immersive/CommandHeader'
import { apiClient, getApiErrorMessage } from '@/lib/api'
import { toast } from 'sonner'
import { Play, Send, Trophy } from 'lucide-react'

type QuestionType = 'behavioral' | 'technical' | 'situational'

interface Question {
  type: string
  question: string
  context?: string
}

interface AnswerFeedback {
  score: number
  rating: string
  tips: string[]
}

interface SessionSummary {
  overall_score: number
  count: number
  rating: string
}

export default function InterviewPage() {
  const [role, setRole] = useState('')
  const [company, setCompany] = useState('')
  const [questionType, setQuestionType] = useState<QuestionType>('behavioral')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null)
  const [questionIndex, setQuestionIndex] = useState(0)
  const [answer, setAnswer] = useState('')
  const [feedbacks, setFeedbacks] = useState<AnswerFeedback[]>([])
  const [summary, setSummary] = useState<SessionSummary | null>(null)

  const startSession = useMutation({
    mutationFn: () =>
      apiClient.post('/interview/session/start', {
        role,
        company: company || undefined,
        question_type: questionType,
      }),
    onSuccess: (res) => {
      setSessionId(res.data.session_id)
      setCurrentQuestion(res.data.question)
      setQuestionIndex(res.data.question_index ?? 0)
      toast.success('Session started!')
    },
    onError: (error) => toast.error(getApiErrorMessage(error, 'Failed to start session')),
  })

  const submitAnswer = useMutation({
    mutationFn: () =>
      apiClient.post(`/interview/session/${sessionId}/answer`, {
        question_index: questionIndex,
        answer_text: answer,
      }),
    onSuccess: (res) => {
      setFeedbacks((prev) => [...prev, res.data.feedback])
      setAnswer('')
      if (res.data.next_question) {
        setCurrentQuestion(res.data.next_question)
        setQuestionIndex(res.data.question_index + 1)
      } else {
        setSummary(res.data.summary)
        setCurrentQuestion(null)
      }
    },
    onError: (error) => toast.error(getApiErrorMessage(error, 'Failed to submit answer')),
  })

  const handleSubmitAnswer = () => {
    if (answer.trim().split(/\s+/).length < 10) {
      toast.error('Please write at least 10 words')
      return
    }
    submitAnswer.mutate()
  }

  if (summary) {
    return (
      <motion.div variants={stagger} initial="hidden" animate="show" className="mx-auto max-w-3xl space-y-6">
        <motion.div variants={fadeUp} className="glass-panel space-y-4 rounded-3xl p-8 text-center">
          <Trophy className="w-12 h-12 mx-auto text-warning" />
          <h1 className="text-2xl font-bold">Session Complete</h1>
          <p className="text-4xl font-bold">{summary.overall_score}/100</p>
          <p className="text-sm text-muted-foreground capitalize">{summary.rating} · {summary.count} questions answered</p>
        </motion.div>
        {feedbacks.length > 0 && (
          <motion.div variants={fadeUp} className="glass-panel space-y-3 rounded-3xl p-6">
            <h2 className="font-semibold text-sm">Feedback Recap</h2>
            {feedbacks.map((fb, i) => (
              <div key={i} className="p-3 bg-muted rounded-lg text-sm space-y-1">
                <span className="font-medium capitalize">Q{i + 1}: {fb.score}/100 ({fb.rating})</span>
                <ul className="list-disc pl-5 space-y-0.5">
                  {fb.tips.map((tip, j) => <li key={j}>{tip}</li>)}
                </ul>
              </div>
            ))}
          </motion.div>
        )}
      </motion.div>
    )
  }

  if (!sessionId) {
    return (
      <motion.div variants={stagger} initial="hidden" animate="show" className="mx-auto max-w-3xl space-y-8">
        <CommandHeader
          eyebrow="AI Workflow"
          title="Interview Coach"
          description="Start a live practice loop, submit answers, and get score-backed feedback."
        />
        <motion.div variants={fadeUp} className="glass-panel space-y-4 rounded-3xl p-6">
          <input
            type="text"
            placeholder="Target Role *"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm"
            required
          />
          <input
            type="text"
            placeholder="Company (optional)"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            className="w-full rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm"
          />
          <fieldset className="space-y-2">
            <legend className="font-medium text-sm">Question Type</legend>
            {(['behavioral', 'technical', 'situational'] as QuestionType[]).map((type) => (
              <label key={type} className="flex items-center gap-2 text-sm capitalize">
                <input
                  type="radio"
                  name="questionType"
                  value={type}
                  checked={questionType === type}
                  onChange={() => setQuestionType(type)}
                />
                {type}
              </label>
            ))}
          </fieldset>
          <LiquidGlassButton
            onClick={() => startSession.mutate()}
            disabled={!role.trim() || startSession.isPending}
            className="w-full"
          >
            <Play className="w-4 h-4 mr-2" />
            {startSession.isPending ? 'Starting...' : 'Start Session'}
          </LiquidGlassButton>
        </motion.div>
      </motion.div>
    )
  }

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="mx-auto max-w-3xl space-y-6">
      {currentQuestion && (
        <motion.div variants={fadeUp} className="glass-panel space-y-4 rounded-3xl p-6">
          <p className="text-sm text-muted-foreground">Question {feedbacks.length + 1}</p>
          <p className="text-lg font-medium">{currentQuestion.question}</p>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Type your answer (minimum 10 words)..."
            rows={5}
            className="w-full resize-none rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm"
          />
          <LiquidGlassButton
            onClick={handleSubmitAnswer}
            disabled={submitAnswer.isPending}
          >
            <Send className="w-4 h-4 mr-2" />
            {submitAnswer.isPending ? 'Submitting...' : 'Submit Answer'}
          </LiquidGlassButton>
        </motion.div>
      )}
      {feedbacks.length > 0 && (
        <motion.div variants={fadeUp} className="glass-panel space-y-3 rounded-3xl p-6">
          <h2 className="font-semibold text-sm">Previous Feedback</h2>
          {feedbacks.map((fb, i) => (
            <div key={i} className="p-3 bg-muted rounded-lg text-sm space-y-1">
              <span className="font-medium capitalize">Q{i + 1}: {fb.score}/100 ({fb.rating})</span>
              <ul className="list-disc pl-5 space-y-0.5">
                {fb.tips.map((tip, j) => <li key={j}>{tip}</li>)}
              </ul>
            </div>
          ))}
        </motion.div>
      )}
    </motion.div>
  )
}
