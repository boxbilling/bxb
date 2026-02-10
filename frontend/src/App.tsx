import { Routes, Route } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import HomePage from './pages/HomePage.tsx'
import UserProfilePage from './pages/UserProfilePage'
import LoginPage from './pages/LoginPage'

function App() {
  return (
    <Routes>
      {/* Pages with MainLayout (header + footer) */}
      <Route element={<MainLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/profile" element={<UserProfilePage />} />
      </Route>

      {/* Pages without layout */}
      <Route path="/login" element={<LoginPage />} />
    </Routes>
  )
}

export default App
