import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuthStore, tokenToUser } from '../store/authStore'
import { authService } from '../services/auth.service'
import { getErrorMessage } from '@/shared/types/api'
import type { RegisterData } from '@/shared/types/auth'

export function useRegister() {
  const [isLoading, setIsLoading] = useState(false)
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  async function register(data: RegisterData) {
    setIsLoading(true)
    try {
      const { access_token } = await authService.register(data)
      const user = tokenToUser(access_token, data.email)
      if (!user) throw new Error('Token inválido')

      try {
        const fullUser = await authService.getCurrentUser()
        setAuth(fullUser, access_token)
      } catch {
        setAuth(user, access_token)
      }

      toast.success('Cuenta creada exitosamente')
      navigate('/dashboard')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  return { register, isLoading }
}
