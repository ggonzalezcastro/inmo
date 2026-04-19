import { ChatInterface } from '../components/ChatInterface'

export function ChatPage() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0">
        <div className="h-[calc(100vh-4rem)] min-h-[600px]">
          <ChatInterface />
        </div>
      </div>
    </div>
  )
}
