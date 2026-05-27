'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { fadeUp, stagger } from '@/lib/motion-variants'
import { LiquidGlassButton } from '@/components/ui/LiquidGlassButton'
import { apiClient } from '@/lib/api'
import { toast } from 'sonner'
import { Play, Send, Trophy } from 'lucide-react'

type QuestionType = 'behavioral' | 'technical' | 'situational'

interface Question {
  id: string
  text: string
}

interface AnswerFeedback {
  score: number
  feedback: string
}

interface SessionSummary {
  overall_score: number
  strengths: string[]
  improvements: string[]
}

export default function InterviewPage() {
  const [role, setRole] = useState('')
  const [company, setCompany] = useState('')
  const [questionType, setQuestionType] = useState<QuestionType>('behavioral')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null)
  const [answer, setAnswer] = useState('')
  const [feedbacks, setFeedbacks] = useState<AnswerFeedback[]>([])
  const [summary, setSummary] = useState<SessionSummary | null>(null)

  const startSession = useMutation({
    mutationFn: () =>
      apiClient.post('/api/v1/interview/session/start', {
        role,
        company: company || undefined,
        question_type: questionType,
      }),
    onSuccess: (res) => {
      setSessionId(res.data.session_id)
      setCurrentQuestion(res.data.question)
      toast.success('Session started!')
    },
    onError: () => toast.error('Failed to start session'),
  })

  const submitAnswer = useMutation({
    mutationFn: () =>
      apiClient.post(`/api/v1/interview/session/${sessionId}/answer`, {
        question_id: currentQuestion?.id,
        answer,
      }),
    onSuccess: (res) => {
      setFeedbacks((prev) => [...prev, res.data.feedback])
      setAnswer('')
      if (res.data.next_question) {
        setCurrentQuestion(res.data.next_question)
      } else {
        setSummary(res.data.summary)
        setCurrentQuestion(null)
      }
    },
    onError: () => toast.error('Failed to submit answer'),
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
      <motion.div variants={stagger} initial="hidden" animate="show" className="max-w-2xl mx-auto p-6 space-y-6">
        <motion.div variants={fadeUp} className="text-center space-y-4">
          <Trophy className="w-12 h-12 mx-auto text-yellow-500" />
          <h1 className="text-2xl font-bold">Session Complete</h1>
          <p className="text-4xl font-bold">{summary.overall_score}/100</p>
        </motion.div>
        <motion.div variants={fadeUp} className="space-y-3">
          <h2 className="font-semibold">Strengths</h2>
          <ul className="list-disc pl-5 space-y-1">
            {summary.strengths.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
          <h2 className="font-semibold">Areas to Improve</h2>
          <ul className="list-disc pl-5 space-y-1">
            {summary.improvements.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </motion.div>
      </motion.div>
    )
  }

  if (!sessionId) {
    return (
      <motion.div variants={stagger} initial="hidden" animate="show" className="max-w-md mx-auto p-6 space-y-6">
        <motion.h1 variants={fadeUp} className="text-2xl font-bold">Interview Coach</motion.h1>
        <motion.div variants={fadeUp} className="space-y-4">
          <input
            type="text"
            placeholder="Target Role *"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg"
            required
          />
          <input
            type="text"
            placeholder="Company (optional)"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg"
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
    <motion.div variants={stagger} initial="hidden" animate="show" className="max-w-2xl mx-auto p-6 space-y-6">
      {currentQuestion && (
        <motion.div variants={fadeUp} className="space-y-4">
          <p className="text-sm text-muted-foreground">Question {feedbacks.length + 1}</p>
          <p className="text-lg font-medium">{currentQuestion.text}</p>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Type your answer (minimum 10 words)..."
            rows={5}
            className="w-full px-3 py-2 border rounded-lg resize-none"
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
        <motion.div variants={fadeUp} className="space-y-3 border-t pt-4">
          <h2 className="font-semibold text-sm">Previous Feedback</h2>
          {feedbacks.map((fb, i) => (
            <div key={i} className="p-3 bg-muted rounded-lg text-sm">
              <span className="font-medium">Q{i + 1}: {fb.score}/100</span> — {fb.feedback}
            </div>
          ))}
        </motion.div>
      )}
    </motion.div>
  )
}
