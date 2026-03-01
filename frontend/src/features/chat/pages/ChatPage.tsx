// ⚠️ Chat page wrapper — ChatTest.jsx is NOT modified
// This page wraps the original ChatTest component within the new AppShell layout
import ChatTest from '../../../components/ChatTest'

export function ChatPage() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0">
        <div className="h-[calc(100vh-4rem)] min-h-[600px]">
          <ChatTest />
        </div>
      </div>
    </div>
  )
}
