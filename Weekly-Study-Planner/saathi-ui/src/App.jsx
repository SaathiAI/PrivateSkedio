import { useEffect, useState } from "react";
import { AuthProvider } from "./components/Auth.jsx";
import { LandingPage } from "./components/LandingPage.jsx";
import { StudyPlanApp } from "./components/StudyPlanApp.jsx";

function AppRouter() {
  const [hash, setHash] = useState(() => window.location.hash || "");

  useEffect(() => {
    const syncHash = () => setHash(window.location.hash || "");
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  if (hash === "#app") {
    return <StudyPlanApp />;
  }

  return <LandingPage />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}
