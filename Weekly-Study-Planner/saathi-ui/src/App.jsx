import { AuthProvider } from "./components/Auth.jsx";
import { StudyPlanApp } from "./components/StudyPlanApp.jsx";

export default function App() {
  return (
    <AuthProvider>
      <StudyPlanApp />
    </AuthProvider>
  );
}
