import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'

export default function AppLayout() {
  return (
    <div className="flex min-h-screen bg-surface-50">
      <div className="lg:flex lg:flex-row flex-col w-full">
        <Navbar />
        <main className="flex-1 overflow-auto bg-surface-50">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
