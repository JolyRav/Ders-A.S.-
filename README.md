# Kişisel Ders Asistanım (iPad uyumlu)

Bu uygulama Safari üzerinden açılan bir web uygulamasıdır. iPad'e Python kurman gerekmez.

## Özellikler
- PDF, DOCX, TXT ve MD ders notlarını yükleme
- Notları Supabase bulut depolamasında kalıcı saklama
- Soru metniyle notlarda ilgili bölümleri bulma
- Fotoğraf olarak yüklenen çoktan seçmeli soruları okuma ve notlara göre çözme
- Seçenekleri tek tek açıklama ve kaynak dosya/parça gösterme
- Uygulama şifresi

> Not: PDF'nin kendisi taranmış fotoğraflardan oluşuyorsa metin çıkarımı yapılamayabilir. OCR uygulanmış PDF yükle. Kaynak gösterimi dosya ve metin parçası düzeyindedir; metin çıkarımı sayfa numarasını her zaman korumaz.

## Ücretsiz başlangıç altyapısı
- Streamlit Community Cloud: uygulamayı barındırır.
- Supabase Free: notları ve metin parçalarını saklar.
- OpenAI API: yalnızca soru-cevap ve metin vektörleştirme kullanımına göre ücretlenir.

Ücretsiz servislerin limitleri ve şartları değişebilir. Supabase Free projeleri bir süre etkinlik olmadığında duraklatılabilir.

## Kurulum (bir kez bilgisayardan veya iPad tarayıcısından)

1. GitHub hesabı aç ve yeni, **Private** bir repository oluştur.
2. Bu ZIP içindeki dosyaları repository'ye yükle.
3. Supabase'de yeni proje oluştur.
4. Supabase > SQL Editor'e girip `supabase_schema.sql` içeriğini çalıştır.
5. Supabase > Storage bölümünde `ders-notlari` isimli **private** bucket oluştur.
6. Supabase Project Settings > API bölümünden Project URL ve `service_role` key'i al. `service_role` key gizlidir; GitHub'a koyma.
7. OpenAI Platform'da API key oluştur. ChatGPT/Gemini aboneliği API kullanımını kapsamaz; API ayrıca kullanım bazlı ücretlenir.
8. Streamlit Community Cloud'a GitHub ile giriş yap, private repository'ni seç ve `app.py` dosyasını ana dosya olarak belirt.
9. Streamlit uygulama ayarlarında **Secrets** alanına aşağıdakileri ekle:

```toml
APP_PASSWORD = "kendine-ait-uzun-bir-sifre"
OPENAI_API_KEY = "sk-..."
SUPABASE_URL = "https://proje-kimligi.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "supabase-service-role-key"
```

10. Uygulama erişimini Streamlit ayarlarında private tut. Yalnızca kendi hesabınla erişecek şekilde ayarla. Uygulama içi şifre ikinci bir koruma katmanıdır.

## Maliyet kontrolü
OpenAI API ücretleri kullandığın modele ve token miktarına göre değişir. OpenAI Platform'da billing/usage limitlerini ayrıca ayarla. İlk aşamada düşük bir aylık limit belirle. Uygulamadaki modeller:
- Yanıt: `gpt-4.1-mini`
- Embedding: `text-embedding-3-small`

## Önemli güvenlik notları
- API anahtarlarını `app.py` içine yazma.
- `service_role` anahtarını GitHub'a yükleme veya kimseyle paylaşma.
- GitHub repository'sini public yapma.
- Supabase projesi kişisel ders notlarını barındırır; hesabında güçlü parola ve mümkünse iki aşamalı doğrulama kullan.
- Bu örnek kişisel kullanım için hazırlanmıştır. Yüksek güvenlik gerektiren hassas/kişisel verileri yükleme.
