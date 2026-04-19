import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuthStore, tokenToUser } from '../store/authStore'
import { authService } from '../services/auth.service'
import { getErrorMessage } from '@/shared/types/api'
import type { LoginCredentials } from '@/shared/types/auth'

export function useLogin() {
  const [isLoading, setIsLoading] = useState(false)
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  async function login(credentials: LoginCredentials) {
    setIsLoading(true)
    try {
      const { access_token } = await authService.login(credentials)
      const user = tokenToUser(access_token, credentials.email)
      if (!user) throw new Error('Token inválido')

      // Set auth immediately so the token is available for subsequent requests
      setAuth(user, access_token)

      // Enrich with full user profile from DB (token is now set)
      try {
        const fullUser = await authService.getCurrentUser()
        setAuth(fullUser, access_token)
      } catch {
        // Fall through — decoded token data already set above
      }

      navigate('/dashboard')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  return { login, isLoading }
}
